# v0.2 experimental conversion engine

Requires Python 3.10+ (standard library only).

Run:

```powershell
python bridge_v02.py "input.3mf" --reference-scad "original_calibration.3mf" --reference-bs "bambu_calibration.3mf" -o "converted.3mf"
```

The calibration OpenSCAD file and Bambu Studio project must contain the **same geometry and triangle order**, and must cover every input color. For the initial wreath test, use `pine_bells_wreath_v1.1.6(2).3mf` and `pine_bells_wreath_v1.1.6.bs.3mf` as the calibration pair.

The script generates new painted mesh geometry from its input. It reuses printer profiles, placement, thumbnails, and other project metadata from the Bambu template. **Experimental:** the generated file has not yet been opened and sliced in Creality Print 7.1. Check positioning, filament mapping, mesh warnings, and print settings. Do not print without inspecting the slice preview.

Limitations: one mesh; uniform triangle colors; existing calibrated colors only; no automatic placement or CFS assignment; template thumbnail may be stale. It does not repair non-manifold meshes.
