# OpenSCAD 3MF Bridge v0.4 (experimental)

Converts an OpenSCAD multicolor 3MF to a Bambu-style painted project that can be opened in Creality Print. Supports **up to four colors** and multiple untransformed mesh objects, without Boolean union.

## Usage

```powershell
python .\bridge.py .\4Color.3mf -o .\4Color-converted.3mf
```

Keep `template.3mf` next to `bridge.py`. Python standard library only.

## Tests

```powershell
python -m unittest discover -s tests -v
```

The four-color sample fixture is from OpenSCAD. The test verifies 32 vertices, 48 faces, four paint codes, four filament colors, and removal of incompatible slicer settings. A second test checks three-color filament trimming.

## Limitations

- Slot 4 paint code `1C` is known from the prior wreath reference, but **this four-color output has not yet been validated in Creality Print**.
- Filament order is the order of first color appearance in the source's build items; CFS slot assignment is done in the slicer.
- Build-item transforms, component objects, per-vertex color gradients, and more than four colors are unsupported.
- Bundled template retains Bambu metadata, printer profile, and stale thumbnails. Verify printer, filament, model placement, and slice preview.
- `template.3mf` is an example Bambu Studio project and may contain project-specific metadata. The converter is not yet template-free.
