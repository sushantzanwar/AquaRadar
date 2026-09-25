"""Water surface extent from a 10 m mask."""

PIXEL_AREA_M2 = 100.0


def extent_m2(water_pixels: int, pixel_area_m2: float = PIXEL_AREA_M2) -> float:
    return float(water_pixels) * float(pixel_area_m2)


def extent_hectares(water_pixels: int, pixel_area_m2: float = PIXEL_AREA_M2) -> float:
    """Hectares for 10 m pixels: count x 100 m2, then converted from square metres."""
    return extent_m2(water_pixels, pixel_area_m2) / 10_000.0
