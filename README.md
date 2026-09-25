# AquaWatch

Satellite water-quality and contamination intelligence prototype. It monitors cached Sentinel-2 scenes, flags relative anomalies in water extent, turbidity, chlorophyll-a, and transparency, and ranks zones for ground sampling.

Outputs are decision support, not laboratory results. Every product includes a confidence score and a lab-verification disclaimer. The demo runs offline from `data/`.

The directory tree, file-level descriptions, and phased build order are in [docs/ARCHITECTURE.md](docs/ARCHITECTURE.md).

The folders from that tree are on disk. Each directory contains a `.gitkeep` so Git retains it. Python, TypeScript, config, corpus, and notebook files are not added yet. Scene folders under `data/scenes/{water_body_id}/{YYYYMMDD}/` are created when cached Sentinel-2 scenes are added.
