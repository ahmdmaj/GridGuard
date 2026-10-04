import datetime
import pandas as pd
from experiments.run_ablation import run_ablation_variant
from intelligence.forecast.rule import RuleForecastService

def run_sensitivity():
    print("Running Sensitivity Analysis (Tornado Chart Data)...")
    
    base_scenario = {
        "bg_peak_kw": 500.0,
        "sags": [
            {"start": datetime.datetime(2026, 1, 1, 18, 0, 0), "duration_s": 4*3600, "depth": 1.0}
        ]
    }
    
    forecaster = RuleForecastService()
    
    # Base run
    res_base = run_ablation_variant("Base", base_scenario, use_baseline=False, forecaster=forecaster)
    
    results = []
    
    # Battery Size
    scenario_batt_low = dict(base_scenario)
    scenario_batt_low["battery_capacity_kwh"] = 20.0
    res = run_ablation_variant("Batt_20kWh", scenario_batt_low, use_baseline=False, forecaster=forecaster)
    results.append({"Parameter": "Battery", "Value": "20 kWh", "Unmet (kWh)": res["Unmet Critical (kWh)"], "Fuel (L)": res["Fuel Used (L)"]})
    
    scenario_batt_high = dict(base_scenario)
    scenario_batt_high["battery_capacity_kwh"] = 80.0
    res = run_ablation_variant("Batt_80kWh", scenario_batt_high, use_baseline=False, forecaster=forecaster)
    results.append({"Parameter": "Battery", "Value": "80 kWh", "Unmet (kWh)": res["Unmet Critical (kWh)"], "Fuel (L)": res["Fuel Used (L)"]})
    
    # Sag Duration
    scenario_dur_short = dict(base_scenario)
    scenario_dur_short["sags"] = [{"start": datetime.datetime(2026, 1, 1, 18, 0, 0), "duration_s": 2*3600, "depth": 1.0}]
    res = run_ablation_variant("Dur_2h", scenario_dur_short, use_baseline=False, forecaster=forecaster)
    results.append({"Parameter": "Duration", "Value": "2 h", "Unmet (kWh)": res["Unmet Critical (kWh)"], "Fuel (L)": res["Fuel Used (L)"]})

    scenario_dur_long = dict(base_scenario)
    scenario_dur_long["sags"] = [{"start": datetime.datetime(2026, 1, 1, 18, 0, 0), "duration_s": 8*3600, "depth": 1.0}]
    res = run_ablation_variant("Dur_8h", scenario_dur_long, use_baseline=False, forecaster=forecaster)
    results.append({"Parameter": "Duration", "Value": "8 h", "Unmet (kWh)": res["Unmet Critical (kWh)"], "Fuel (L)": res["Fuel Used (L)"]})

    df = pd.DataFrame(results)
    print("\n--- Sensitivity Results ---")
    print(df.to_string(index=False))
    df.to_csv("results/phase3/sensitivity.csv", index=False)

if __name__ == "__main__":
    run_sensitivity()
