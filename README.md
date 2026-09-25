# AquaWatch

Satellite water-quality and contamination intelligence prototype. It monitors cached Sentinel-2 scenes, flags relative anomalies in water extent, turbidity, chlorophyll-a, and transparency, and ranks zones for ground sampling.

Outputs are decision support, not laboratory results. Every product includes a confidence score and a lab-verification disclaimer. The demo runs offline from `data/`.

The directory tree, file-level descriptions, and phased build order are in [docs/ARCHITECTURE.md](docs/ARCHITECTURE.md). No pipeline code is in the tree yet.
