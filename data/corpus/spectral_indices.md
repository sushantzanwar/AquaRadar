# Spectral indices and water extent

NDWI in this pipeline is (B3 − B8) / (B3 + B8), using Sentinel-2 green and near-infrared. Pixels above the configured threshold (default 0) are the NDWI water cross-check.

The primary mask is the local model `giswqs/s2-water-unetplusplus-efficientnet-b4`: UNet++ with an EfficientNet-B4 encoder, six bands in the order B2, B3, B4, B8, B11, B12, tiles of 512×512, classes background and water. Weights are read from disk. They are not downloaded during a request.

Agreement is the fraction of valid pixels where the model mask and the NDWI mask match. Agreement below the configured floor lowers confidence and records `model_agreement`. If the weights are missing, the mask is NDWI only and confidence records `segmentation_model_unavailable`.

Water surface extent is the count of water pixels multiplied by the pixel area. On a 10 m grid that area is 100 m². Extent is stored per zone as well as for the whole clipped scene.
