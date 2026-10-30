# OpenSCAD 3MF Bridge v0.3.2 — experimental filament mapping

This prototype assigns up to three detected colors to filament slots **1, 2, 3** rather than 2, 3, 4. It trims the four-entry filament arrays, adjusts the flush volume arrays, and removes inherited AMS slot metadata.

**Important:** Slot-1 `paint_color=4` is inferred from the observed codes for slots 2 and 3. It has **not yet been validated in Creality Print**. Do not print until you inspect the sliced filament assignments.

## Usage

```powershell
python .\bridge.py .\Untitled.3mf -o .\test_blocks_v032.3mf
```

Keep `template.3mf` beside `bridge.py`. Requires Python 3.9+; no pip packages.

## Acceptance test

1. Import the included `three_blocks_v032_experimental.3mf` in Creality Print 7.1. Confirm exactly 3 model filaments appear, and red/blue/green blocks are correct.
2. Slice and verify all 3 blocks use their respective filament assignments. Do not use Auto Mapping until checking the initial model filament list.
3. Import `wreath_v032_experimental.3mf`, verify white/green/red, slice and inspect letters and color transitions.
4. Click Auto Mapping and note whether the three model filaments map to expected CFS slots. This mapping is determined by installed spools and may change displayed colors.

## Limitations

Uses a bundled Bambu project template with inherited slicer settings, thumbnails and plate placement. Supports build-referenced meshes with uniform per-triangle OpenSCAD colors, no transforms or component objects, and at most three colors. The filament-1 paint code and compatibility are unverified. This release is for import testing, not production printing.
