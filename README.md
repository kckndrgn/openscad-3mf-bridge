# OpenSCAD 3MF Bridge v0.3.1 (experimental)

Adds support for multiple mesh objects referenced by the 3MF build list.

## Run

```powershell
python bridge.py "Untitled.3mf" -o "test_blocks.3mf"
```

Place `template.3mf` next to `bridge.py`. Python 3.9+; no third-party packages.

The converter combines build-referenced meshes into one *mesh resource* by
concatenating vertices and rebasing triangle indices. It does not perform a
Boolean union, so disconnected parts remain disconnected geometrically.

Current limitations:
- Maximum three distinct uniform triangle colors.
- Build-item transforms and component objects are not supported (clear error).
- The template carries inherited printer/profile information; verify your
  Creality Hi printer profile and CFS mappings before slicing.
- Template thumbnails are stale; do not rely on their preview images.
- Color compatibility must be tested in Creality Print 7.1.

The `get_mesh` helper remains for validating the single output mesh.
