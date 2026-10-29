# OpenSCAD 3MF Bridge

Experimental research project to translate OpenSCAD 3MF per-triangle colors into multicolor slicer projects compatible with Creality Print.

## Current status: reference validation prototype (v0.1.0)

**Important:** This first version is **not yet a standalone converter**. It validates that an OpenSCAD export and a known-good Bambu Studio project contain the same geometry, derives their color/paint mapping, and outputs a copy of the validated Bambu Studio project. It intentionally refuses mismatched models. This provides a reproducible baseline for developing the real conversion stage without claiming unsupported generality.

Python 3.10+; standard library only.

```powershell
python bridge.py "pine_bells_wreath_v1.1.6(2).3mf" --reference "pine_bells_wreath_v1.1.6.bs.3mf" --output "wreath_verified.3mf"
```

Open `wreath_verified.3mf` in Creality Print and map the filaments to the CFS. Verify slice preview before printing.

## Planned milestones

- [x] Verify topology and triangle-color correspondence between OpenSCAD and Bambu Studio exports.
- [x] Safely package a known-good reference project.
- [ ] Generate Bambu/Creality face-paint encoding for arbitrary OpenSCAD meshes without a Bambu reference.
- [ ] Generate a minimal valid slicer project with filament metadata, placement, and geometry.
- [ ] Support multiple objects, transformations, mixed vertex colors, and nonuniform triangle properties.
- [ ] Test Creality Print 7.1 import, slicing, and CFS filament mapping across different models.
- [ ] Add Windows Explorer integration or an OpenSCAD export shortcut.

## Safety

Never overwrite original models. A 3MF project can contain printer and filament presets from another slicer; keep your Creality Hi profile and verify all print settings when importing. This utility does not repair meshes.

## Repository setup

Create an empty GitHub repository named `openscad-3mf-bridge`, then copy this directory into it and run:

```bash
git init
git add .
git commit -m "Initial reference validation prototype"
git branch -M main
git remote add origin https://github.com/YOUR-USERNAME/openscad-3mf-bridge.git
git push -u origin main
```

The provided example 3MF files are test fixtures, not required for distribution; do not commit them unless you intend to publish the model and associated slicer presets.
