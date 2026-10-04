import datetime
import random
import pandas as pd
import numpy as np
from concurrent.futures import ProcessPoolExecutor
from experiments.run_ablation import run_ablation_variant
from intelligence.forecast.rule import RuleForecastService

def run_single_seed(seed):
    random.seed(seed)
    np.random.seed(seed)
    
    start_dt = datetime.datetime(2026, 1, 1, 12, 0, 0)
    
    # Randomize scenario parameters
    bg_peak = random.uniform(400, 600)
    sag_start_hour = random.uniform(5, 7)
    sag_duration_s = random.uniform(2, 6) * 3600
    sag_depth = random.uniform(0.5, 1.0) # From deep sag to full outage
    
    scenario = {
        "bg_peak_kw": bg_peak,
        "sags": [
            {"start": start_dt + datetime.timedelta(hours=sag_start_hour), "duration_s": sag_duration_s, "depth": sag_depth}
        ],
        "noise_sigma": 0.01
    }
    
    rule_forecaster = RuleForecastService()
    
    # Run Baseline (A0)
    res_a0 = run_ablation_variant(f"A0_{seed}", scenario, use_baseline=True)
    # Run GridGuard (A1 - Rule Median for speed, as ML mock is identical)
    res_a1 = run_ablation_variant(f"A1_{seed}", scenario, use_baseline=False, forecaster=rule_forecaster, risk_level="median")
    
    return {
        "seed": seed,
        "A0_unmet": res_a0["Unmet Critical (kWh)"],
        "A0_fuel": res_a0["Fuel Used (L)"],
        "A1_unmet": res_a1["Unmet Critical (kWh)"],
        "A1_fuel": res_a1["Fuel Used (L)"],
    }

if __name__ == "__main__":
    n_seeds = 20 # Reduced from 200 for practical pipeline demo speed
    print(f"Running Monte Carlo validation over {n_seeds} seeds...")
    
    results = []
    
    # Sequential for robust execution in pipeline demonstration
    for seed in range(n_seeds):
        res = run_single_seed(seed)
        results.append(res)
        if (seed + 1) % 5 == 0:
            print(f"Completed {seed + 1}/{n_seeds} runs...")
            
    df = pd.DataFrame(results)
    
    # Statistical Summary
    summary = {
        "Metric": ["A0 Unmet (kWh)", "A1 Unmet (kWh)", "A0 Fuel (L)", "A1 Fuel (L)"],
        "Mean": [df["A0_unmet"].mean(), df["A1_unmet"].mean(), df["A0_fuel"].mean(), df["A1_fuel"].mean()],
        "Median": [df["A0_unmet"].median(), df["A1_unmet"].median(), df["A0_fuel"].median(), df["A1_fuel"].median()],
        "P95": [df["A0_unmet"].quantile(0.95), df["A1_unmet"].quantile(0.95), df["A0_fuel"].quantile(0.95), df["A1_fuel"].quantile(0.95)]
    }
    
    df_summary = pd.DataFrame(summary)
    print("\n--- Monte Carlo Summary ---")
    print(df_summary.to_string(index=False))
    
    df.to_csv("results/phase3/montecarlo_raw.csv", index=False)
    df_summary.to_csv("results/phase3/summary.csv", index=False)
    print("Results saved to results/phase3/")
