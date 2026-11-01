"""Experimental standalone OpenSCAD colored-3MF to Bambu/Creality project.

Requires the bundled template. Supports 1+ build-referenced meshes, 1-4 uniform face colors.
No reference files or third-party Python dependencies are needed.
"""
import argparse
from collections import Counter
import json
import math
from pathlib import Path
import xml.etree.ElementTree as ET
import zipfile

CORE = '{http://schemas.microsoft.com/3dmanufacturing/core/2015/02}'
MAT = '{http://schemas.microsoft.com/3dmanufacturing/material/2015/02}'
ET.register_namespace('', CORE[1:-1])
ET.register_namespace('m', MAT[1:-1])
ET.register_namespace('p', 'http://schemas.microsoft.com/3dmanufacturing/production/2015/06')
ET.register_namespace('BambuStudio', 'http://schemas.bambulab.com/package/2021')

# Experimental: codes 8 and 0C verified for slots 2 and 3;
# code 4 for slot 1 is inferred and requires Creality Print validation.
PAINT_SLOTS = [(1, '4'), (2, '8'), (3, '0C'), (4, '1C')]

# Slicer-specific settings that Creality Print 7.1 replaces with warnings.
# Omitting them allows the importing slicer to choose its own defaults.
INCOMPATIBLE_SETTINGS = {
    'ensure_vertical_shell_thickness',
    'filament_map_mode',
    'locked_skeleton_infill_pattern',
    'locked_skin_infill_pattern',
}


def get_mesh(root):
    meshes = root.findall(f'.//{CORE}object/{CORE}mesh')
    if len(meshes) != 1:
        raise ValueError(f'Only one mesh is supported (found {len(meshes)})')
    mesh = meshes[0]
    return mesh, list(mesh.find(f'{CORE}vertices')), list(mesh.find(f'{CORE}triangles'))


def parse_transform(value):
    """3MF 4x3 affine matrix, in row-vector order; translation is last row."""
    if value is None:
        return (1.,0.,0., 0.,1.,0., 0.,0.,1., 0.,0.,0.)
    try:
        values = tuple(float(v) for v in value.split())
    except ValueError as exc:
        raise ValueError(f'Invalid build-item transform: {value!r}') from exc
    if len(values) != 12 or not all(math.isfinite(v) for v in values):
        raise ValueError('Build-item transform must contain 12 finite numbers')
    return values


def transform_vertex(vertex, matrix):
    x, y, z = (float(vertex.get(k)) for k in ('x','y','z'))
    a,b,c,d,e,f,g,h,i,tx,ty,tz = matrix
    return ET.Element(f'{CORE}vertex', {
        'x': format(x*a+y*d+z*g+tx, '.12g'),
        'y': format(x*b+y*e+z*h+ty, '.12g'),
        'z': format(x*c+y*f+z*i+tz, '.12g'),
    })


def compose_transforms(inner, outer):
    """Apply inner first, then outer, using 3MF row-vector matrices."""
    result = []
    for row in range(3):
        for col in range(3):
            result.append(sum(inner[row * 3 + k] * outer[k * 3 + col] for k in range(3)))
    for col in range(3):
        result.append(sum(inner[9 + k] * outer[k * 3 + col] for k in range(3)) + outer[9 + col])
    return tuple(result)


def transform_determinant(m):
    a,b,c,d,e,f,g,h,i,*_ = m
    return a*(e*i-f*h)-b*(d*i-f*g)+c*(d*h-e*g)


def get_source_meshes(root):
    """Flatten mesh and nested component instances, preserving face colors."""
    objects = {obj.get('id'): obj for obj in root.findall(f'./{CORE}resources/{CORE}object')}
    build = root.find(f'{CORE}build')
    if build is None or not build.findall(f'{CORE}item'):
        raise ValueError('3MF has no build items')
    vertices, triangles = [], []
    identity = parse_transform(None)

    def expand(object_id, matrix, ancestors):
        if object_id in ancestors:
            raise ValueError(f'Circular component reference: {" -> ".join(ancestors + (object_id,))}')
        obj = objects.get(object_id)
        if obj is None:
            raise ValueError(f'3MF references missing object {object_id}')
        mesh = obj.find(f'{CORE}mesh')
        components = obj.find(f'{CORE}components')
        if mesh is not None and components is not None:
            raise ValueError(f'Object {object_id} contains both mesh and components')
        if mesh is not None:
            v_node, t_node = mesh.find(f'{CORE}vertices'), mesh.find(f'{CORE}triangles')
            if v_node is None or t_node is None:
                raise ValueError(f'Object {object_id} mesh is missing vertices or triangles')
            det = transform_determinant(matrix)
            if abs(det) < 1e-12:
                raise ValueError('Transform collapses the mesh (singular matrix)')
            offset = len(vertices)
            local = list(v_node)
            vertices.extend(transform_vertex(v, matrix) for v in local)
            for tri in t_node:
                attrs = dict(tri.attrib)
                for key in ('v1', 'v2', 'v3'):
                    index = int(attrs[key])
                    if index < 0 or index >= len(local):
                        raise ValueError(f'Invalid triangle vertex index in object {object_id}')
                    attrs[key] = str(index + offset)
                if det < 0:
                    attrs['v2'], attrs['v3'] = attrs['v3'], attrs['v2']
                triangles.append(ET.Element(f'{CORE}triangle', attrs))
        elif components is not None:
            for component in components.findall(f'{CORE}component'):
                if component.get('path'):
                    raise ValueError('Cross-part component references are not supported yet')
                child = component.get('objectid')
                if not child:
                    raise ValueError(f'Component in object {object_id} lacks objectid')
                child_matrix = parse_transform(component.get('transform'))
                expand(child, compose_transforms(child_matrix, matrix), ancestors + (object_id,))
        else:
            raise ValueError(f'Object {object_id} has neither mesh nor components')

    for item in build.findall(f'{CORE}item'):
        if item.get('path'):
            raise ValueError('Cross-part build references are not supported yet')
        expand(item.get('objectid'), compose_transforms(identity, parse_transform(item.get('transform'))), ())
    return vertices, triangles


def extract_colors(root, triangles):
    groups = {}
    for group in root.findall(f'.//{MAT}colorgroup'):
        groups[group.get('id')] = [entry.get('color').upper() for entry in group]
    result = []
    for tri in triangles:
        pid, p1 = tri.get('pid'), tri.get('p1')
        if pid not in groups or p1 is None:
            raise ValueError('Expected OpenSCAD colorgroup face assignments (pid/p1)')
        if any(tri.get(key, p1) != p1 for key in ('p2', 'p3')):
            raise ValueError('Per-vertex color gradients are not supported')
        result.append(groups[pid][int(p1)])
    return result


def convert(source, output, template=None):
    source, output = Path(source), Path(output)
    template = Path(template) if template else Path(__file__).with_name('template.3mf')
    if not template.exists():
        raise FileNotFoundError(f'Missing bundled template: {template}')
    if len({source.resolve(), output.resolve(), template.resolve()}) != 3:
        raise ValueError('Input, output, and template paths must differ')

    with zipfile.ZipFile(source) as zin:
        root = ET.fromstring(zin.read('3D/3dmodel.model'))
    vertices, triangles = get_source_meshes(root)
    if not vertices or not triangles:
        raise ValueError('Input mesh is empty')
    face_colors = extract_colors(root, triangles)
    # First-appearance ordering is stable and avoids assigning unused palette colors.
    palette = list(dict.fromkeys(face_colors))
    if len(palette) > 4:
        raise ValueError(f'At most 4 distinct face colors supported; found {len(palette)}')
    assignments = {color: PAINT_SLOTS[i] for i, color in enumerate(palette)}

    with zipfile.ZipFile(template) as zin:
        model = ET.fromstring(zin.read('3D/Objects/object_1.model'))
        bs_mesh, _, _ = get_mesh(model)
        vertex_node, triangle_node = bs_mesh.find(f'{CORE}vertices'), bs_mesh.find(f'{CORE}triangles')
        vertex_node.clear()
        triangle_node.clear()
        # Bambu's known-good template uses Z -2 in object coordinates and
        # +2 in its assembly transform, preserving the input's Z coordinates.
        for v in vertices:
            ET.SubElement(vertex_node, f'{CORE}vertex', {
                'x': v.get('x'), 'y': v.get('y'),
                'z': format(float(v.get('z')) - 2.0, '.9g')
            })
        for face, color in zip(triangles, face_colors):
            ET.SubElement(triangle_node, f'{CORE}triangle', {
                **{k: face.get(k) for k in ('v1', 'v2', 'v3')},
                'paint_color': assignments[color][1]
            })

        settings = json.loads(zin.read('Metadata/project_settings.config'))
        for key in INCOMPATIBLE_SETTINGS:
            settings.pop(key, None)
        # Trim all filament-indexed arrays, not only filament_colour.
        # This prevents a phantom fourth material and stale slicer mappings.
        count = len(palette)
        for key, value in list(settings.items()):
            if key.startswith('filament_') and isinstance(value, list) and len(value) == 4:
                settings[key] = value[:count]
        settings['filament_colour'] = [color[:7] for color in palette]
        settings['filament_multi_colour'] = [color[:7] for color in palette]
        settings['filament_type'] = ['PLA'] * count
        settings['filament_self_index'] = [str(i + 1) for i in range(count)]
        # Filament-related purge arrays must match the new filament count.
        if isinstance(settings.get('flush_volumes_matrix'), list):
            matrix = settings['flush_volumes_matrix']
            if len(matrix) == 16:
                settings['flush_volumes_matrix'] = [matrix[r * 4 + c]
                    for r in range(count) for c in range(count)]
        if isinstance(settings.get('flush_volumes_vector'), list):
            vector = settings['flush_volumes_vector']
            if len(vector) == 8:
                settings['flush_volumes_vector'] = vector[:2 * count]
        # This Bambu metadata describes the four original AMS slots.
        # Remove it rather than advertise nonexistent slots.
        settings.pop('extruder_ams_count', None)
        model_config = ET.fromstring(zin.read('Metadata/model_settings.config'))
        # The template also stores filament_map_mode as plate metadata.
        # Remove it rather than importing a Bambu-specific value.
        for parent in model_config.iter():
            for child in list(parent):
                if child.tag == 'metadata' and child.get('key') in INCOMPATIBLE_SETTINGS:
                    parent.remove(child)
        for elem in model_config.iter():
            if 'face_count' in elem.attrib:
                elem.set('face_count', str(len(triangles)))
            if elem.tag == 'metadata' and elem.get('key') == 'source_file':
                elem.set('value', source.name)

        with zipfile.ZipFile(output, 'w', compression=zipfile.ZIP_DEFLATED) as zout:
            for info in zin.infolist():
                data = zin.read(info.filename)
                if info.filename == '3D/Objects/object_1.model':
                    data = ET.tostring(model, encoding='utf-8', xml_declaration=True)
                elif info.filename == 'Metadata/project_settings.config':
                    data = json.dumps(settings, ensure_ascii=False).encode('utf-8')
                elif info.filename == 'Metadata/model_settings.config':
                    data = ET.tostring(model_config, encoding='utf-8', xml_declaration=True)
                zout.writestr(info.filename, data)

    with zipfile.ZipFile(output) as check:
        assert check.testzip() is None
        generated = ET.fromstring(check.read('3D/Objects/object_1.model'))
        _, out_vertices, out_triangles = get_mesh(generated)
        assert len(out_vertices) == len(vertices) and len(out_triangles) == len(triangles)
    print(f'Created: {output}')
    print(f'Geometry: {len(vertices)} vertices, {len(triangles)} triangles')
    for color, count in Counter(face_colors).items():
        slot, paint = assignments[color]
        print(f'  {color}: {count} faces -> filament slot {slot} (paint {paint})')
    print('EXPERIMENTAL: Verify all filament colors and sliced toolpaths in Creality Print.')
    print('Template thumbnails and printer configuration are inherited; do not trust them.')


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('input', help='OpenSCAD colored 3MF export')
    parser.add_argument('-o', '--output', required=True)
    parser.add_argument('--template', help='Override bundled project template')
    args = parser.parse_args()
    source = Path(args.input)
    template = Path(args.template) if args.template else Path(__file__).with_name('template.3mf')
    if not source.is_file():
        parser.exit(2, f"Error: Input file not found: {source}\n")
    if not template.is_file():
        parser.exit(2, f"Error: Template file not found: {template}\n")
    try:
        convert(source, args.output, template)
    except zipfile.BadZipFile:
        parser.exit(2, "Error: Invalid or corrupted 3MF archive.\n")
    except KeyError as exc:
        parser.exit(2, f"Error: Missing required 3MF entry: {exc}\n")
    except ET.ParseError as exc:
        parser.exit(2, f"Error: Invalid 3MF XML: {exc}\n")
    except ValueError as exc:
        parser.exit(2, f"Error: {exc}\n")
    except OSError as exc:
        parser.exit(2, f"Error: File operation failed: {exc}\n")

if __name__ == '__main__':
    main()
