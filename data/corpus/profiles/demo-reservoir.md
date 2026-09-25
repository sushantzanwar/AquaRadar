# Demo Reservoir

Demo Reservoir is a synthetic water body used to exercise the offline pipeline. It is not an operational monitoring site.

Two zones are defined. The north basin lies next to the demo intake. The south basin lies farther from that intake and closer to the demo settlement. Rankings should prefer the north basin when severity and persistence are similar, because intake proximity has the higher weight.

Seasonal baselines have to be fit from cached scenes with `scripts/fit_seasonal_baselines.py` before a date can be scored. Dropping a new `YYYYMMDD` folder under `data/scenes/demo-reservoir/` makes that acquisition visible without a code change.
