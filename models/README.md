# Water segmentation weights

Local cache for `giswqs/s2-water-unetplusplus-efficientnet-b4` (UNet++ with an EfficientNet-B4 encoder, 6-band 512×512 tiles, classes background and water).

Download once, before the demo, into this folder:

```
huggingface-cli download giswqs/s2-water-unetplusplus-efficientnet-b4 --local-dir models/s2-water-unetplusplus-efficientnet-b4
```

The API refuses to download weights on a request (`model.allow_download` is false). If this folder has no weights, segmentation falls back to NDWI and lowers confidence with reason `segmentation_model_unavailable`.
