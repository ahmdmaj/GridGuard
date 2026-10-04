import datetime
import pandas as pd
import json

from physical.plant import PhysicalPlant
from physical.feeder import SagEvent
from intelligence.baseline import BaselineController, BaselineHysteresisController
from intelligence.decision_engine import DecisionEngine
from metrics.esh import ESHCalculator
from digital_twin.state import DigitalTwinState, GridState, SolarState, BatteryState, GeneratorState, LoadState
from intelligence.forecast.rule import RuleForecastService
from intelligence.forecast.ml import MLForecastService
from metrics.provenance import get_provenance

def run_ablation_variant(variant_name, scenario_config, controller_type="GG", forecaster=None, risk_level="median"):
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
        "non_essential_kw": 2.0,
        "watchdog_s": 90.0
    }
    
    plant = PhysicalPlant(config)
    for sag in scenario_config.get("sags", []):
        plant.feeder.add_sag_event(SagEvent(sag["start"], sag["duration_s"], sag["depth"]))
        
    if controller_type == "A0":
        controller = BaselineController()
    elif controller_type == "B1":
        controller = BaselineHysteresisController()
    else:
        controller = DecisionEngine(config)
        esh_calc = ESHCalculator(config)
        
    current_time = datetime.datetime(2026, 1, 1, 12, 0, 0)
    dt_s = 60.0 # 1-min steps for speed
    end_time = datetime.datetime(2026, 1, 2, 0, 0, 0)
    
    metrics = {
        "Variant": variant_name,
        "Unmet Critical (kWh)": 0.0,
        "Fuel Used (L)": 0.0,
        "V Out-of-band (s)": 0.0,
        "Transfers": 0,
        "SOC at 18:30": 0.0
    }
    
    last_sts_state = "GRID_PASS"
    initial_fuel = plant.generator.fuel_liters
    telemetry_history = []
    
    while current_time < end_time:
        telemetry = {
            "ts": current_time.isoformat() + "Z",
            "v_rms_pu": plant.v_pcc_pu,
            "grid_connected": True,
            "soc": plant.battery.soc,
            "fuel_liters": plant.generator.fuel_liters,
            "gen_available": True
        }
        telemetry_history.append(telemetry)
        if len(telemetry_history) > 24:
            telemetry_history.pop(0)
            
        cmd = None
        if controller_type in ["A0", "B1"]:
            cmd = controller.evaluate(dt_s, (current_time - datetime.datetime(2026, 1, 1, 12, 0)).total_seconds(), telemetry)
        else:
            fb = forecaster.forecast(telemetry_history, current_time, 12*3600)
            
            # Convert bundle to forecast list for ESH
            forecast_list = []
            steps = len(fb.grid_ok_prob)
            solar_key = "p10" if risk_level == "pessimistic" else "p50"
            load_key = "p90" if risk_level == "pessimistic" else "p50"
            
            for i in range(steps):
                forecast_list.append({
                    "solar_kw": float(fb.solar_kw[solar_key][i]),
                    "load_critical_kw": float(fb.load_kw[load_key][i]),
                    "load_important_kw": 3.0,
                    "load_flexible_kw": 2.0,
                    "grid_ok_prob": float(fb.grid_ok_prob[i])
                })
                
            twin_state = DigitalTwinState(
                timestamp=telemetry["ts"],
                grid=GridState(voltage_pu=telemetry["v_rms_pu"], is_available=telemetry["grid_connected"]),
                solar=SolarState(power_kw=plant.solar.power_kw if hasattr(plant.solar, 'power_kw') else 0.0),
                battery=BatteryState(soc=telemetry["soc"]),
                generator=GeneratorState(fuel_liters=telemetry["fuel_liters"], is_available=telemetry["gen_available"]),
                loads=LoadState(critical_kw=4.0, important_kw=3.0, flexible_kw=2.0)
            )
                
            expected_esh = esh_calc.calculate_forecast_esh(twin_state, forecast_list, assume_island=False)
            shadow_esh = esh_calc.calculate_forecast_esh(twin_state, forecast_list, assume_island=True)
            cmd = controller.evaluate(dt_s, (current_time - datetime.datetime(2026, 1, 1, 12, 0)).total_seconds(), telemetry, expected_esh, shadow_esh)

        res = plant.step(dt_s, current_time, cmd)
        telem = res["plant_telem"]
        
        if telem["unserved_kw"] > 0:
            print(f"[{current_time}] UNSERVED: {telem['unserved_kw']:.2f}kW, SOC={telem['soc']:.1f}%, Gen={telem['sts_state']}, Load={telem['load_critical_kw']:.1f}, Cmd={cmd}")
        metrics["Unmet Critical (kWh)"] += (telem["unserved_kw"] * (dt_s / 3600.0))
        if telem["v_crit_pu"] < 0.94 or telem["v_crit_pu"] > 1.06:
            metrics["V Out-of-band (s)"] += dt_s
            
        if telem["sts_state"] != last_sts_state:
            metrics["Transfers"] += 1
            last_sts_state = telem["sts_state"]
            
        if current_time.hour == 18 and current_time.minute == 30 and current_time.second < dt_s:
            metrics["SOC at 18:30"] = telem["soc"]
            
        current_time += datetime.timedelta(seconds=dt_s)
        
    metrics["Fuel Used (L)"] = initial_fuel - plant.generator.fuel_liters
    return metrics

if __name__ == "__main__":
    start_dt = datetime.datetime(2026, 1, 1, 12, 0, 0)
    scenario = {
        "bg_peak_kw": 500.0,
        "sags": [
            {"start": start_dt + datetime.timedelta(hours=6), "duration_s": 4*3600, "depth": 1.0} # 4h outage
        ]
    }
    
    print("Running Ablation Study (Scenario S4: Sag then Outage)...")
    
    rule_forecaster = RuleForecastService()
    ml_forecaster = MLForecastService()
    
    res_a0 = run_ablation_variant("A0: Baseline", scenario, controller_type="A0")
    print("Finished A0")
    res_b1 = run_ablation_variant("B1: Baseline Hysteresis", scenario, controller_type="B1")
    print("Finished B1")
    res_a1 = run_ablation_variant("A1: GG Rule Median", scenario, controller_type="GG", forecaster=rule_forecaster, risk_level="median")
    print("Finished A1")
    res_a2 = run_ablation_variant("A2: GG ML Median", scenario, controller_type="GG", forecaster=ml_forecaster, risk_level="median")
    print("Finished A2")
    res_a3 = run_ablation_variant("A3: GG ML Pessimistic", scenario, controller_type="GG", forecaster=ml_forecaster, risk_level="pessimistic")
    print("Finished A3")
    
    df = pd.DataFrame([res_a0, res_b1, res_a1, res_a2, res_a3])
    df.to_csv("results/phase2/ablation.csv", index=False)
    
    prov = get_provenance(scenario)
    with open("results/phase2/ablation.provenance.json", "w") as f:
        json.dump(prov, f, indent=2)
        
    print("\n--- Ablation Results ---")
    print(df.to_string(index=False))
