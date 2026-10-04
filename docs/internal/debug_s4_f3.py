import datetime
from experiments.run_ablation import run_ablation_variant
from intelligence.forecast.rule import RuleForecastService

start_dt = datetime.datetime(2026, 1, 1, 12, 0, 0)
scenario = {
    "bg_peak_kw": 500.0,
    "sags": [
        {"start": start_dt + datetime.timedelta(hours=6), "duration_s": 4*3600, "depth": 1.0}
    ]
}

forecaster = RuleForecastService()
print("Running A1 GridGuard...")
res = run_ablation_variant("A1", scenario, use_baseline=False, forecaster=forecaster, risk_level="median")

print("\nA1 Results:", res)
