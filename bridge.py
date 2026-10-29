"""Experimental OpenSCAD 3MF -> Bambu/Creality project conversion.

Uses a known-good Bambu Studio project as a template and a matching OpenSCAD
export as calibration. Single mesh, uniform per-face color only.
"""
import argparse
from collections import Counter
from pathlib import Path
import zipfile
import xml.etree.ElementTree as ET

CORE = '{http://schemas.microsoft.com/3dmanufacturing/core/2015/02}'
MAT = '{http://schemas.microsoft.com/3dmanufacturing/material/2015/02}'
ET.register_namespace('', CORE[1:-1])
ET.register_namespace('m', MAT[1:-1])
ET.register_namespace('p', 'http://schemas.microsoft.com/3dmanufacturing/production/2015/06')
ET.register_namespace('BambuStudio', 'http://schemas.bambulab.com/package/2021')


def read_model(path, member):
    with zipfile.ZipFile(path) as z:
        return ET.fromstring(z.read(member))


def mesh(root):
    objects = root.findall(f'.//{CORE}object')
    meshes = [o.find(f'{CORE}mesh') for o in objects]
    meshes = [m for m in meshes if m is not None]
    if len(meshes) != 1:
        raise ValueError(f'Expected exactly one mesh, found {len(meshes)}')
    m = meshes[0]
    return m, list(m.find(f'{CORE}vertices')), list(m.find(f'{CORE}triangles'))


def colors(root, triangles):
    groups = {int(g.get('id')): [c.get('color').upper() for c in g] for g in root.findall(f'.//{MAT}colorgroup')}
    result = []
    for tri in triangles:
        pid = int(tri.get('pid', '0'))
        p1 = tri.get('p1')
        if pid not in groups or p1 is None or any(tri.get(k, p1) != p1 for k in ('p2', 'p3')):
            raise ValueError('Only uniform per-triangle colorgroup colors are supported')
        result.append(groups[pid][int(p1)])
    return result


def convert(source, reference_scad, reference_bs, output):
    if Path(output).resolve() in {Path(source).resolve(), Path(reference_bs).resolve()}:
        raise ValueError('Output must not overwrite an input')
    source_root = read_model(source, '3D/3dmodel.model')
    ref_root = read_model(reference_scad, '3D/3dmodel.model')
    bs_root = read_model(reference_bs, '3D/Objects/object_1.model')
    _, src_vertices, src_triangles = mesh(source_root)
    _, ref_vertices, ref_triangles = mesh(ref_root)
    bs_mesh, bs_vertices, bs_triangles = mesh(bs_root)
    if len(ref_vertices) != len(bs_vertices) or len(ref_triangles) != len(bs_triangles):
        raise ValueError('Calibration geometry counts differ')
    # A stronger correspondence check than counts alone: vertex order and face indices.
    for a, b in zip(ref_triangles, bs_triangles):
        if any(a.get(k) != b.get(k) for k in ('v1', 'v2', 'v3')):
            raise ValueError('Calibration triangle ordering differs')
    mapping = {}
    for color, tri in zip(colors(ref_root, ref_triangles), bs_triangles):
        paint = tri.get('paint_color')
        if not paint:
            raise ValueError('Calibration Bambu mesh lacks paint_color')
        if color in mapping and mapping[color] != paint:
            raise ValueError(f'Inconsistent paint encoding for {color}')
        mapping[color] = paint
    src_colors = colors(source_root, src_triangles)
    unknown = set(src_colors) - set(mapping)
    if unknown:
        raise ValueError(f'Colors not in calibration: {sorted(unknown)}. Recalibrate using a reference project with these colors.')
    # Bambu's template vertices were offset in Z by -2mm; retain its original
    # build transform by applying the same reference-derived vertex translation.
    offsets = []
    for axis in ('x', 'y', 'z'):
        deltas = [float(b.get(axis)) - float(a.get(axis)) for a, b in zip(ref_vertices, bs_vertices)]
        delta = sum(deltas) / len(deltas)
        if any(abs(d - delta) > 0.001 for d in deltas):
            raise ValueError('Calibration geometry is not a simple translation')
        offsets.append(delta)
    verts_node = bs_mesh.find(f'{CORE}vertices')
    tris_node = bs_mesh.find(f'{CORE}triangles')
    verts_node.clear(); tris_node.clear()
    for v in src_vertices:
        ET.SubElement(verts_node, f'{CORE}vertex', {axis: format(float(v.get(axis)) + offsets[i], '.8g') for i, axis in enumerate(('x','y','z'))})
    for tri, color in zip(src_triangles, src_colors):
        ET.SubElement(tris_node, f'{CORE}triangle', {k: tri.get(k) for k in ('v1','v2','v3')} | {'paint_color': mapping[color]})
    with zipfile.ZipFile(reference_bs) as zin, zipfile.ZipFile(output, 'w') as zout:
        for item in zin.infolist():
            data = zin.read(item.filename)
            if item.filename == '3D/Objects/object_1.model':
                data = ET.tostring(bs_root, encoding='utf-8', xml_declaration=True)
            elif item.filename == 'Metadata/model_settings.config':
                config = ET.fromstring(data)
                for e in config.iter():
                    if 'face_count' in e.attrib:
                        e.set('face_count', str(len(src_triangles)))
                data = ET.tostring(config, encoding='utf-8', xml_declaration=True)
            elif item.filename.startswith('Metadata/') and item.filename.endswith('.png'):
                # Template thumbnails are misleading for new geometry: leave them
                # out only in future project-format iteration; current prototype
                # preserves all references to ensure slicer import compatibility.
                pass
            zout.writestr(item, data)
    print('Converted:', output)
    print('Vertices:', len(src_vertices), 'Triangles:', len(src_triangles))
    print('Colors:', dict(Counter(src_colors)))
    print('Calibration:', mapping)
    print('WARNING: Template printer settings, placement and thumbnails retained. Verify before slicing.')


def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument('input')
    p.add_argument('--reference-scad', required=True)
    p.add_argument('--reference-bs', required=True)
    p.add_argument('-o', '--output', required=True)
    a = p.parse_args()
    convert(a.input, a.reference_scad, a.reference_bs, a.output)

if __name__ == '__main__':
    main()
