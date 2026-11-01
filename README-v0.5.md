# v0.5 experimental: 3MF build-item transforms

Adds translation, rotation, nonuniform scale, and mirrored-mesh winding correction.
Includes the previously tested user-friendly missing-file CLI handling.
3MF transforms are 4x3 **row-vector** matrices: translation is entries 10-12.
The earlier `4Color_transforms_test.3mf` used a different matrix layout;
use `tests/fixtures/four_colors_transforms.3mf` from this package instead.

Run:
`python bridge.py tests/fixtures/four_colors_transforms.3mf -o converted.3mf`

Tests:
`python -m unittest discover -s tests -v`

Still unsupported: component assemblies and referenced meshes in other model parts.
Do not commit until Creality Print has validated the generated result.
