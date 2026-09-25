# Cached inputs

Runtime reads this tree. It does not download satellite scenes.

```
data/scenes/{water_body_id}/{YYYYMMDD}/
  B02.tif  B03.tif  B04.tif  B08.tif  B11.tif  B12.tif  SCL.tif
```

Optional red-edge bands `B05.tif` and `B06.tif` enable the Dall'Olmo / Gitelson chlorophyll index. Without them, chlorophyll is reported as unavailable and fusion uses extent and turbidity only.

Bands should be Sentinel-2 L2A. A metric CRS with a 10 m grid makes extent equal to water-pixel count times 100 m². Geographic scenes still run; pixel area is then estimated from the pixel size at the scene latitude and the confidence note records that.

`B11` and `B12` may be 20 m. Preprocessing resamples them onto the 10 m grid.

The API may write masks, indicator rasters, baselines, credit uploads, and the corpus index under `data/cache/`, `data/baselines/`, and `data/credits/`. It does not modify `data/scenes/`.
