#!/usr/bin/env python3
"""Reference-based OpenSCAD -> Bambu/Creality 3MF paint transfer (prototype).

Requires a Bambu Studio project created from the SAME geometry. This is deliberately
not a general-purpose slicer project generator yet.
"""
import argparse
import collections
import copy
import json
from pathlib import Path
import sys
import zipfile
import xml.etree.ElementTree as ET

CORE = '{http://schemas.microsoft.com/3dmanufacturing/core/2015/02}'


def extract(path, name):
    with zipfile.ZipFile(path) as z:
        return z.read(name)


def mesh_data(xml):
    root = ET.fromstring(xml)
    vertices = root.findall('.//' + CORE + 'vertex')
    triangles = root.findall('.//' + CORE + 'triangle')
    return vertices, triangles


def convert(source, reference, output):
    if Path(source).resolve() == Path(output).resolve() or Path(reference).resolve() == Path(output).resolve():
        raise ValueError('Output must not overwrite either input')
    with zipfile.ZipFile(source) as z:
        src_model = z.read('3D/3dmodel.model')
    with zipfile.ZipFile(reference) as z:
        ref_mesh_name = '3D/Objects/object_1.model'
        ref_model = z.read(ref_mesh_name)
        config = json.loads(z.read('Metadata/project_settings.config'))
        original_members = [(i, z.read(i.filename)) for i in z.infolist()]
    sv, st = mesh_data(src_model)
    rv, rt = mesh_data(ref_model)
    if len(sv) != len(rv) or len(st) != len(rt):
        raise ValueError('Reference project geometry counts do not match OpenSCAD export')
    # Bambu Studio may recenter the mesh and shift Z; verify all vertices match
    # within a single translation, allowing normal floating-point export noise.
    shift = [float(rv[0].get(axis)) - float(sv[0].get(axis)) for axis in 'xyz']
    for i, (a, b) in enumerate(zip(sv, rv)):
        if any(abs(float(b.get(axis)) - float(a.get(axis)) - delta) > 0.001
               for axis, delta in zip('xyz', shift)):
            raise ValueError(f'Vertex {i} differs: not the same mesh')
    for i, (a, b) in enumerate(zip(st, rt)):
        if tuple(a.get(k) for k in ('v1', 'v2', 'v3')) != tuple(b.get(k) for k in ('v1', 'v2', 'v3')):
            raise ValueError(f'Triangle {i} differs: not the same mesh')
    # Learn paint codes from matching triangles in the reference, rather than
    # assuming that a paint code means the same filament in every project.
    color_to_paint = collections.defaultdict(collections.Counter)
    for a, b in zip(st, rt):
        color = (a.get('pid'), a.get('p1'), a.get('p2'), a.get('p3'))
        if color[1] is None or color[2] is not None or color[3] is not None:
            raise ValueError('Only uniform per-triangle colors are supported')
        paint = b.get('paint_color')
        if paint is None:
            raise ValueError('Reference mesh has unpainted triangles')
        color_to_paint[color][paint] += 1
    mapping = {}
    for color, counts in color_to_paint.items():
        if len(counts) != 1:
            raise ValueError(f'Inconsistent paint mapping for {color}: {dict(counts)}')
        mapping[color] = next(iter(counts))
    # The prototype copies the verified project unchanged: geometry and paint
    # were checked triangle-by-triangle above. It does NOT invent new metadata.
    with zipfile.ZipFile(output, 'w') as z:
        for info, data in original_members:
            z.writestr(copy.copy(info), data)
    return mapping, config.get('filament_colour', [])


def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument('openscad_3mf', type=Path)
    p.add_argument('--reference', required=True, type=Path, help='Working Bambu Studio project of SAME geometry')
    p.add_argument('--output', required=True, type=Path)
    args = p.parse_args()
    try:
        mapping, colors = convert(args.openscad_3mf, args.reference, args.output)
    except (ValueError, KeyError, zipfile.BadZipFile, ET.ParseError, OSError) as e:
        p.exit(1, f'Error: {e}\n')
    print('Validated source/reference geometry and paint mapping:')
    for k, v in sorted(mapping.items()):
        print(f'  source color group {k[0]}, index {k[1]} -> paint {v}')
    print('Reference filament colors:', ', '.join(colors))
    print(f'Wrote verified project copy: {args.output}')
    print('NOTE: Prototype validates and packages an existing working project; it does not yet convert arbitrary geometry.')


if __name__ == '__main__':
    main()
