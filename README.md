# OpenSCAD 3MF Bridge v0.3 (experimental)

Converts **single-mesh OpenSCAD 3MF** with **up to 3 solid face colors** into a painted Bambu Studio-style project that may import into Creality Print 7.1.

Unlike v0.2, no reference OpenSCAD or Bambu files are needed per conversion. The distribution includes a **fixed known-good project template** derived from the wreath test. This is **not** a fully template-independent 3MF writer.

## Run

Requires Python 3.9+; no pip packages.

```bash
python bridge_v03.py "your-model.3mf" -o "your-model-converted.3mf"
```

Keep `template.3mf` next to `bridge_v03.py`. You can supply a different template using `--template` but its internal structure must match the known-good template.

## Limitations

- One mesh; up to 3 distinct solid face colors. Color groups must have `pid` and `p1` face references.
- Colors assigned to template filament slots 2, 3, 4, in first-seen order. Slot 1 is unused.
- Fixed known-good paint codes `8`, `0C`, `1C` are experimentally validated for those slots **only**.
- Template settings, printer profile, plate position and thumbnails are inherited; images may depict the old wreath. Inspect and adjust in slicer before printing.
- Does not repair bad mesh geometry or handle multi-object 3MF, per-vertex gradients, or color boundaries beyond OpenSCAD's per-face assignments.
- Output is not yet independently verified in Creality Print for arbitrary new models. **Do not print without checking sliced preview and printer profile.**

## Development

Use a feature branch. Keep `template.3mf` as a test fixture, and eventually replace this bundled reference project with a generated minimal project and explicit profile-independent metadata.
