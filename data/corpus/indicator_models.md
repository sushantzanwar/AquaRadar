# Indicator models

Indicators are computed with the `qda_modelos` package and then masked to water pixels. They are relative indexes, not lab-grade concentrations.

Turbidity uses `miller_mckee_2004` on B4 (665 nm, the MSI band nearest the model's red wavelength). In this package the function returns that red reflectance. Compare it with the seasonal baseline. Do not read the number as NTU.

Chlorophyll-a uses `dallolmo_gitelson_rundquist_2003` when B5 and B6 are in the scene folder. The call is (B6, B5, B4), the usual MSI stand-in for the model's ~745 nm, ~725 nm, and 665 nm terms. If those red-edge bands are absent, chlorophyll is omitted and fusion uses extent and turbidity only.

Water transparency uses `giardino_et_al_2001` as B2 / B3 (blue over green). It is reported on the evidence card. The default fusion weights cover extent, turbidity, and chlorophyll, so transparency alone does not raise an alert.

A zone is flagged when one of the fused indicators is more than the configured number of standard deviations from its seasonal baseline (default 3). The fused score is the weighted mean of absolute z-scores, capped for display.
