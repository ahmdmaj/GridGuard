import datetime
import json
import os
from physical.plant import PhysicalPlant
from physical.feeder import SagEvent
from intelligence.baseline import BaselineController
from intelligence.decision_engine import DecisionEngine
from intelligence.esh import ESHCalculator

def generate_rule_forecast(current_time: datetime.datetime, horizon_s: float, step_s: float) -> list:
    """Simple Phase 1 rule-based forecast."""
    # We'll just assume grid is perfectly fine for the forecast in Phase 1 unless the voltage was recently bad
    # For now, let's keep it super simple: assume grid is OK, solar is constant, load is constant.
    forecast = []
    t = current_time
    end_t = current_time + datetime.timedelta(seconds=horizon_s)
    
    # In a real system this would predict the peak window.
    while t < end_t:
        forecast.append({
            "load_critical_kw": 4.0,
            "load_important_kw": 3.0,
            "load_flexible_kw": 2.0,
            "solar_kw": 0.0, # Worst case solar
            "grid_ok_prob": 1.0 # Assume grid is fine
        })
        t += datetime.timedelta(seconds=step_s)
    return forecast

def run_simulation(scenario_id: str, scenario_config: dict, use_baseline: bool) -> dict:
    config = {
        "z_pu": 0.1,
        "p_feeder_rating_kw": 500.0,
        "bg_peak_kw": scenario_config.get("bg_peak_kw", 300.0),
        "noise_sigma_pu": scenario_config.get("noise_sigma", 0.0),
        "inverter_rating_kw": 20.0,
        "battery_capacity_kwh": 40.0,
        "generator_capacity_kw": 15.0,
        "critical_kw": 4.0,
        "important_kw": 3.0,
        "non_essential_kw": 2.0
    }
    
    plant = PhysicalPlant(config)
    
    # Inject Sag Events
    for sag in scenario_config.get("sags", []):
        plant.feeder.add_sag_event(SagEvent(sag["start"], sag["duration_s"], sag["depth"]))
        
    if use_baseline:
        controller = BaselineController()
    else:
        controller = DecisionEngine(config)
        esh_calc = ESHCalculator(config)
        
    current_time = datetime.datetime(2026, 1, 1, 12, 0, 0)
    dt_s = 5.0
    end_time = datetime.datetime(2026, 1, 2, 0, 0, 0) # 12 hours
    
    metrics = {
        "unmet_critical_kwh": 0.0,
        "generator_fuel_l_used": 0.0,
        "time_v_crit_out_of_band_s": 0.0,
        "transfers": 0,
        "total_dropout_ms": 0.0,
        "time_in_support_or_island_s": 0.0,
        "peak_grid_import_kw": 0.0
    }
    
    last_sts_state = "GRID_PASS"
    initial_fuel = plant.generator.fuel_liters
    
    comms_loss = scenario_config.get("comms_loss", False)
    
    while current_time < end_time:
        # Generate telemetry first by stepping with no command? No, telemetry is generated at the end of the previous step.
        # But we need initial telemetry. We can fake the first step or just use the plant's state.
        
        telemetry = {
            "ts": current_time.isoformat() + "Z",
            "v_rms_pu": plant.v_pcc_pu,
            "grid_connected": True, # Feeder model always connects grid unless we add a breaker
            "soc": plant.battery.soc,
            "fuel_liters": plant.generator.fuel_liters,
            "gen_available": True
        }
        
        cmd = None
        # Comms loss logic
        is_comms_healthy = True
        if comms_loss and current_time.hour >= 18 and current_time.hour < 20:
            is_comms_healthy = False
            
        if is_comms_healthy:
            if use_baseline:
                cmd = controller.evaluate(dt_s, (current_time - datetime.datetime(2026, 1, 1, 12, 0)).total_seconds(), telemetry)
            else:
                forecast = generate_rule_forecast(current_time, 12*3600, 300)
                expected_esh = esh_calc.calculate_forecast_esh(telemetry, forecast, assume_island=False)
                shadow_esh = esh_calc.calculate_forecast_esh(telemetry, forecast, assume_island=True)
                cmd = controller.evaluate(dt_s, (current_time - datetime.datetime(2026, 1, 1, 12, 0)).total_seconds(), telemetry, expected_esh, shadow_esh)
        
        # Generator fault injection
        if scenario_config.get("gen_fault") and current_time.hour >= 18:
            plant.generator.is_available = False

        res = plant.step(dt_s, current_time, cmd)
        
        # Accumulate metrics
        telem = res["plant_telem"]
        
        metrics["unmet_critical_kwh"] += (telem["unserved_kw"] * (dt_s / 3600.0))
        if telem["v_crit_pu"] < 0.94 or telem["v_crit_pu"] > 1.06:
            metrics["time_v_crit_out_of_band_s"] += dt_s
            
        if telem["sts_state"] != last_sts_state:
            metrics["transfers"] += 1
            last_sts_state = telem["sts_state"]
            
        metrics["total_dropout_ms"] += telem["dropout_ms"]
        
        if telem["sts_state"] in ["SUPPORT", "ISLAND"]:
            metrics["time_in_support_or_island_s"] += dt_s
            
        if plant.last_p_site_kw > metrics["peak_grid_import_kw"]:
            metrics["peak_grid_import_kw"] = plant.last_p_site_kw
            
        current_time += datetime.timedelta(seconds=dt_s)
        
    metrics["generator_fuel_l_used"] = initial_fuel - plant.generator.fuel_liters
    
    return metrics

def main():
    start_dt = datetime.datetime(2026, 1, 1, 12, 0, 0)
    scenarios = {
        "S1_peak_mild_sag": {
            "bg_peak_kw": 450.0, # Pulls voltage down just to ~0.94
        },
        "S2_peak_sustained_uv": {
            "bg_peak_kw": 550.0, # Pulls voltage down to ~0.89 for several hours
        },
        "S4_sag_then_outage": {
            "bg_peak_kw": 500.0,
            "sags": [
                {"start": start_dt + datetime.timedelta(hours=6), "duration_s": 4*3600, "depth": 1.0} # Complete outage at 18:00
            ]
        },
        "S7_comms_loss": {
            "bg_peak_kw": 550.0,
            "comms_loss": True
        }
    }
    
    results = {}
    
    for s_name, s_config in scenarios.items():
        print(f"Running {s_name} with Baseline...")
        base_metrics = run_simulation(s_name, s_config, use_baseline=True)
        print(f"Running {s_name} with GridGuard...")
        gg_metrics = run_simulation(s_name, s_config, use_baseline=False)
        
        results[s_name] = {
            "baseline": base_metrics,
            "gridguard": gg_metrics
        }
        
        # Save individual
        with open(f"results/phase1/{s_name}.json", "w") as f:
            json.dump(results[s_name], f, indent=2)
            
    # Print summary
    print("\n--- PHASE 1 EXPERIMENT SUMMARY ---")
    for s_name, data in results.items():
        base = data["baseline"]
        gg = data["gridguard"]
        print(f"\nScenario: {s_name}")
        print(f"  Critical V out-of-band: Baseline = {base['time_v_crit_out_of_band_s']}s, GridGuard = {gg['time_v_crit_out_of_band_s']}s")
        print(f"  Unmet critical load: Baseline = {base['unmet_critical_kwh']:.3f}kWh, GridGuard = {gg['unmet_critical_kwh']:.3f}kWh")
        print(f"  Transfers: Baseline = {base['transfers']}, GridGuard = {gg['transfers']}")
        print(f"  Gen Fuel: Baseline = {base['generator_fuel_l_used']:.1f}L, GridGuard = {gg['generator_fuel_l_used']:.1f}L")
        
if __name__ == "__main__":
    main()
