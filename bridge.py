"""Experimental standalone OpenSCAD colored-3MF to Bambu/Creality project.

Requires the bundled template. Supports 1+ build-referenced meshes, 1-3 uniform face colors.
No reference files or third-party Python dependencies are needed.
"""
import argparse
from collections import Counter
import json
from pathlib import Path
import xml.etree.ElementTree as ET
import zipfile

CORE = '{http://schemas.microsoft.com/3dmanufacturing/core/2015/02}'
MAT = '{http://schemas.microsoft.com/3dmanufacturing/material/2015/02}'
ET.register_namespace('', CORE[1:-1])
ET.register_namespace('m', MAT[1:-1])
ET.register_namespace('p', 'http://schemas.microsoft.com/3dmanufacturing/production/2015/06')
ET.register_namespace('BambuStudio', 'http://schemas.bambulab.com/package/2021')

# Verified from the wreath project. Slots 2, 3, 4 correspond to these
# per-face paint codes. Slot 1 remains unused by this experimental converter.
PAINT_SLOTS = [(2, '8'), (3, '0C'), (4, '1C')]

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


def get_source_meshes(root):
    """Flatten build-referenced OpenSCAD mesh objects without Boolean union.

    Each object's vertex indices are rebased. Transformed/component objects are
    rejected rather than silently placing them incorrectly.
    """
    objects = {obj.get('id'): obj for obj in root.findall(f'.//{CORE}resources/{CORE}object')}
    build = root.find(f'{CORE}build')
    if build is None or not list(build):
        raise ValueError('3MF has no build items')
    vertices, triangles = [], []
    for item in build.findall(f'{CORE}item'):
        if item.get('transform'):
            raise ValueError('Build item transforms are not supported yet')
        obj = objects.get(item.get('objectid'))
        if obj is None:
            raise ValueError(f"Build references missing object {item.get('objectid')}")
        mesh = obj.find(f'{CORE}mesh')
        if mesh is None:
            raise ValueError('Component objects are not supported yet')
        local_vertices = list(mesh.find(f'{CORE}vertices'))
        local_triangles = list(mesh.find(f'{CORE}triangles'))
        offset = len(vertices)
        vertices.extend(local_vertices)
        for tri in local_triangles:
            attrs = dict(tri.attrib)
            for key in ('v1', 'v2', 'v3'):
                attrs[key] = str(int(attrs[key]) + offset)
            triangles.append(ET.Element(f'{CORE}triangle', attrs))
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
    if len(palette) > 3:
        raise ValueError(f'At most 3 distinct face colors supported; found {len(palette)}')
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
        filament_colors = list(settings['filament_colour'])
        while len(filament_colors) < 4:
            filament_colors.append('#FFFFFF')
        for color, (slot, _) in assignments.items():
            filament_colors[slot - 1] = color[:7]
        settings['filament_colour'] = filament_colors
        settings['filament_type'] = ['PLA'] * len(filament_colors)
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
    print('EXPERIMENTAL: Check printer profile, CFS filament mapping, placement and slice preview.')
    print('Template thumbnails and printer configuration are inherited; do not trust them.')


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('input', help='OpenSCAD colored 3MF export')
    parser.add_argument('-o', '--output', required=True)
    parser.add_argument('--template', help='Override bundled project template')
    args = parser.parse_args()
    convert(args.input, args.output, args.template)

if __name__ == '__main__':
    main()
