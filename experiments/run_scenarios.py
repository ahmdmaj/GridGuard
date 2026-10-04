import datetime
import json
import os
from physical.plant import PhysicalPlant
from physical.feeder import SagEvent
from intelligence.baseline import BaselineController, BaselineHysteresisController
from intelligence.decision_engine import DecisionEngine
from metrics.esh import ESHCalculator
from digital_twin.state import DigitalTwinState, GridState, SolarState, BatteryState, GeneratorState, LoadState
from metrics.provenance import get_provenance

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

def run_simulation(scenario_id: str, scenario_config: dict, controller_type: str) -> dict:
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
        
    if controller_type == "A0":
        controller = BaselineController()
    elif controller_type == "B1":
        controller = BaselineHysteresisController()
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
        "peak_grid_import_kw": 0.0,
        "soc_at_1830": 0.0
    }
    
    last_sts_state = "GRID_PASS"
    initial_fuel = plant.generator.fuel_liters
    
    comms_loss = scenario_config.get("comms_loss", False)
    
    next_forecast_time = current_time
    expected_esh = {}
    shadow_esh = {}
    
    trace_rows = []
    
    while current_time < end_time:
        # Update Solar Availability
        if 8 <= current_time.hour <= 16:
            solar_factor = 0.2 if scenario_config.get("low_solar", False) else 1.0
        else:
            solar_factor = 0.0
        plant.solar.set_availability(solar_factor)
        
        telemetry = {
            "ts": current_time.isoformat() + "Z",
            "v_rms_pu": plant.v_pcc_pu,
            "grid_connected": True,
            "soc": plant.battery.soc,
            "fuel_liters": plant.generator.fuel_liters,
            "gen_available": True
        }
        
        cmd = None
        is_comms_healthy = True
        if comms_loss and current_time.hour >= 18 and current_time.hour < 20:
            is_comms_healthy = False
            
        if is_comms_healthy:
            if controller_type in ["A0", "B1"]:
                cmd = controller.evaluate(dt_s, (current_time - datetime.datetime(2026, 1, 1, 12, 0)).total_seconds(), telemetry)
            else:
                if current_time >= next_forecast_time:
                    forecast = generate_rule_forecast(current_time, 12*3600, 300)
                    
                    twin_state = DigitalTwinState(
                        timestamp=telemetry["ts"],
                        grid=GridState(voltage_pu=telemetry["v_rms_pu"], is_available=telemetry["grid_connected"]),
                        solar=SolarState(power_kw=plant.solar.power_kw if hasattr(plant.solar, 'power_kw') else 0.0),
                        battery=BatteryState(soc=telemetry["soc"]),
                        generator=GeneratorState(fuel_liters=telemetry["fuel_liters"], is_available=telemetry["gen_available"]),
                        loads=LoadState(critical_kw=4.0, important_kw=3.0, flexible_kw=2.0)
                    )
                    
                    expected_esh = esh_calc.calculate_forecast_esh(twin_state, forecast, assume_island=False)
                    shadow_esh = esh_calc.calculate_forecast_esh(twin_state, forecast, assume_island=True)
                    next_forecast_time += datetime.timedelta(seconds=900)
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
            
        if current_time.hour == 18 and current_time.minute == 30 and current_time.second < dt_s:
            metrics["soc_at_1830"] = telem["soc"]
            
        trace_row = {
            "time": telem["ts"],
            "mode": telem["sts_state"],
            "soc": telem["soc"],
            "shadow_esh": shadow_esh.get("critical_only_hours", 0.0) if shadow_esh else 0.0,
            "thresholds": cmd.get("reason", "") if cmd else "",
            "pre_peak": 1 if (16 <= current_time.hour < 18) else 0
        }
        trace_rows.append(trace_row)
            
        current_time += datetime.timedelta(seconds=dt_s)
        
    metrics["generator_fuel_l_used"] = initial_fuel - plant.generator.fuel_liters
    
    # write trace
    import csv
    os.makedirs("results/phase1", exist_ok=True)
    with open(f"results/phase1/{scenario_id}_{controller_type}_trace.csv", "w", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=["time", "mode", "soc", "shadow_esh", "thresholds", "pre_peak"])
        writer.writeheader()
        writer.writerows(trace_rows)
    
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
        "S3_peak_short_sags": {
            "bg_peak_kw": 400.0,
            "sags": [
                {"start": start_dt + datetime.timedelta(hours=6, minutes=10), "duration_s": 5, "depth": 0.2},
                {"start": start_dt + datetime.timedelta(hours=6, minutes=15), "duration_s": 30, "depth": 0.2},
                {"start": start_dt + datetime.timedelta(hours=6, minutes=20), "duration_s": 60, "depth": 0.2}
            ]
        },
        "S4_sag_then_outage": {
            "bg_peak_kw": 500.0,
            "sags": [
                {"start": start_dt + datetime.timedelta(hours=6), "duration_s": 4*3600, "depth": 1.0} # Complete outage at 18:00
            ]
        },
        "S5_sag_low_solar": {
            "bg_peak_kw": 550.0,
            "low_solar": True
        },
        "S6_sag_gen_fault": {
            "bg_peak_kw": 550.0,
            "gen_fault": True
        },
        "S7_comms_loss": {
            "bg_peak_kw": 550.0,
            "comms_loss": True
        },
        "S8_sensor_noise": {
            "bg_peak_kw": 550.0,
            "noise_sigma": 0.05
        },
        "S9_peak_demand_outage": {
            "bg_peak_kw": 600.0, # Will drop voltage, trigger GridGuard, and demand will be high (35kW max supply vs 45kW demand)
            "sags": [
                {"start": start_dt + datetime.timedelta(hours=6), "duration_s": 3600, "depth": 1.0}
            ]
        },
        "S10_extended_peak": {
            "bg_peak_kw": 500.0, 
            "sags": [
                {"start": start_dt + datetime.timedelta(hours=6), "duration_s": 3600, "depth": 1.0}
            ]
        }
    }
    
    results = {}
    
    for s_name, s_config in scenarios.items():
        print(f"Running {s_name} with A0...")
        a0_metrics = run_simulation(s_name, s_config, controller_type="A0")
        print(f"Running {s_name} with B1...")
        b1_metrics = run_simulation(s_name, s_config, controller_type="B1")
        print(f"Running {s_name} with GridGuard...")
        gg_metrics = run_simulation(s_name, s_config, controller_type="GG")
        
        results[s_name] = {
            "A0": a0_metrics,
            "B1": b1_metrics,
            "gridguard": gg_metrics
        }
        
        # Save individual
        results[s_name]["provenance"] = get_provenance(s_config)
        with open(f"results/phase1/{s_name}.json", "w") as f:
            json.dump(results[s_name], f, indent=2)
            
    # Print summary
    print("\n--- PHASE 1 EXPERIMENT SUMMARY ---")
    for s_name, data in results.items():
        a0 = data["A0"]
        b1 = data["B1"]
        gg = data["gridguard"]
        print(f"\nScenario: {s_name}")
        print(f"  Critical V out-of-band: A0 = {a0['time_v_crit_out_of_band_s']}s, B1 = {b1['time_v_crit_out_of_band_s']}s, GridGuard = {gg['time_v_crit_out_of_band_s']}s")
        print(f"  Unmet critical load: A0 = {a0['unmet_critical_kwh']:.3f}kWh, B1 = {b1['unmet_critical_kwh']:.3f}kWh, GridGuard = {gg['unmet_critical_kwh']:.3f}kWh")
        print(f"  SOC at 18:30: A0 = {a0['soc_at_1830']:.1f}%, B1 = {b1['soc_at_1830']:.1f}%, GridGuard = {gg['soc_at_1830']:.1f}%")
        print(f"  Transfers: A0 = {a0['transfers']}, B1 = {b1['transfers']}, GridGuard = {gg['transfers']}")
        print(f"  Gen Fuel: A0 = {a0['generator_fuel_l_used']:.1f}L, B1 = {b1['generator_fuel_l_used']:.1f}L, GridGuard = {gg['generator_fuel_l_used']:.1f}L")
        
if __name__ == "__main__":
    main()
