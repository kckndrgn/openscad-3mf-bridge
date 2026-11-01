# Experimental v0.5 component assemblies

Adds same-part nested component references, instance transforms, repeated mesh instances, cycle detection, and preservation of per-triangle colors. Cross-part references (`path` attributes) remain unsupported.

Run `python bridge.py tests/fixtures/four_colors_components.3mf -o components-converted.3mf`.

Run `python -m unittest discover -s tests -v`.

Please verify the converted result in Creality Print before committing.
