import datetime
import os
import sys
import pandas as pd

# Ensure the root project directory is in the Python path
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from physical.plant import PhysicalPlant
from controller.engine import DecisionEngine
from forecasting.service import MLForecastService
from metrics.esh import ESHCalculator
from digital_twin.state import DigitalTwinState, GridState, SolarState, BatteryState, GeneratorState, LoadState

def run_sensitivity():
    soc_levels = [10.0, 20.0, 40.0, 60.0, 80.0, 100.0]
    demand_levels = [4.0, 10.0, 20.0, 30.0, 40.0, 50.0, 60.0]
    
    config = {
        "z_pu": 0.1,
        "p_feeder_rating_kw": 500.0,
        "inverter_rating_kw": 20.0,
        "battery_capacity_kwh": 40.0,
        "battery_max_discharge_kw": 20.0,
        "generator_capacity_kw": 15.0,
        "generator_fuel_rate_l_per_kwh": 0.3,
        "bg_peak_kw": 0.0,
        "noise_sigma_pu": 0.0,
        "esh_threshold_hours": 24.0,
        "generator_start_esh_hours": 4.0,
        "shed_flexible_esh": 6.0,
    }
    
    dt_s = 300.0
    dt_hours = dt_s / 3600.0
    
    results = []
    
    # Preload services
    forecast_service = MLForecastService(model_path="ml/models/forecast_model.joblib")
    esh_calc = ESHCalculator(config)
    
    # Create the 2D Grid structure for ASCII
    grid_map = {}
    
    print("\nRunning Sensitivity Analysis Matrix (1 Hour Midnight Simulation)...")
    
    for demand in demand_levels:
        grid_map[demand] = {}
        for soc in soc_levels:
            # Reinitialize plant and engine
            plant = PhysicalPlant(config)
            engine = DecisionEngine(config)
            
            # Scenario setup
            plant.battery.current_energy_kwh = config["battery_capacity_kwh"] * (soc / 100.0)
            plant.generator.is_available = False # Generator offline
            plant.generator.fuel_liters = 0.0
            
            crit_val = demand * 0.4
            imp_val = demand * 0.3
            flex_val = demand * 0.3
            
            plant.loads.nominal_kw["critical"] = crit_val
            plant.loads.nominal_kw["important"] = imp_val
            plant.loads.nominal_kw["non_essential"] = flex_val
            
            plant.v_pcc_pu = 0.0 # Grid is OFF
            
            # Start in ISLAND mode to avoid transfer dropout penalty on first step
            from physical.inverter_sts import InverterMode
            plant.inverter.current_mode = InverterMode.ISLAND
            
            unserved_crit = 0.0
            unserved_imp = 0.0
            unserved_flex = 0.0
            total_hardware_unserved = 0.0
            
            current_time = datetime.datetime(2026, 1, 1, 0, 0, 0) # Midnight
            next_forecast = current_time
            expected_esh = {}
            shadow_esh = {}
            
            for step in range(12): # 1 hour = 12 steps
                # Force physical values
                plant.solar.power_kw = 0.0 
                plant.v_pcc_pu = 0.0 
                
                telem = {
                    "ts": current_time.isoformat() + "Z",
                    "v_rms_pu": 0.0,
                    "grid_connected": False,
                    "soc": plant.battery.soc,
                    "fuel_liters": 0.0,
                    "gen_available": False
                }
                
                twin_state = DigitalTwinState(
                    timestamp=telem["ts"],
                    grid=GridState(voltage_pu=0.0, is_available=False),
                    solar=SolarState(power_kw=0.0),
                    battery=BatteryState(soc=telem["soc"]),
                    generator=GeneratorState(fuel_liters=0.0, is_available=False, power_kw=0.0),
                    loads=LoadState(
                        critical_kw=crit_val,
                        important_kw=imp_val,
                        flexible_kw=flex_val
                    )
                )
                
                if current_time >= next_forecast:
                    forecasts = forecast_service.generate_forecast(twin_state, 12 * 12)
                    
                    # Create battery_only copy
                    import copy
                    bat_twin = copy.deepcopy(twin_state)
                    bat_twin.generator.is_available = False
                    
                    expected_esh = esh_calc.calculate_forecast_esh(twin_state, forecasts, assume_island=False)
                    shadow_esh = esh_calc.calculate_forecast_esh(bat_twin, forecasts, assume_island=True)
                    next_forecast += datetime.timedelta(minutes=15)
                    
                cmd = engine.evaluate(twin_state, expected_esh, shadow_esh)
                
                flex_shed = not cmd.get("connect_flexible", True)
                imp_shed = not cmd.get("connect_important", True)
                
                shed_tier = 0
                if flex_shed and imp_shed:
                    shed_tier = 2
                elif flex_shed:
                    shed_tier = 1
                    
                plant_cmd = {
                    "inverter_mode": "ISLAND",
                    "shed_tier": shed_tier,
                    "gen_cmd": "STOP"
                }
                
                step_telem = plant.step(dt_s, current_time, plant_cmd)["plant_telem"]
                
                unserved_crit += max(0.0, crit_val - step_telem["load_critical_kw"]) * dt_hours
                unserved_imp += max(0.0, imp_val - step_telem["load_important_kw"]) * dt_hours
                unserved_flex += max(0.0, flex_val - step_telem["load_flexible_kw"]) * dt_hours
                total_hardware_unserved += step_telem["unserved_kw"] * dt_hours
                
                current_time += datetime.timedelta(seconds=dt_s)
                
            # Classify
            final_crit_unserved = unserved_crit + total_hardware_unserved
            
            if final_crit_unserved > 0.001:
                status = "[ FAIL ]"
            elif unserved_flex > 0.001 or unserved_imp > 0.001:
                status = "[DEGRADED]"
            else:
                status = "[  OK  ]"
                
            grid_map[demand][soc] = status
            
            results.append({
                "Demand_kW": demand,
                "SOC_%": soc,
                "Status": status.strip("[] "),
                "Unserved_Crit_kWh": final_crit_unserved,
                "Unserved_Imp_kWh": unserved_imp,
                "Unserved_Flex_kWh": unserved_flex
            })
            
    # Print the ASCII Map
    print("\n" + "="*70)
    print("GRIDGUARD OPERATING ENVELOPE (1 HR HORIZON)".center(70))
    print("="*70)
    
    header = "Demand (kW) | " + " | ".join([f"{int(s):>8}% SOC" for s in soc_levels])
    print(header)
    print("-" * len(header))
    
    for demand in demand_levels:
        row_str = f"{int(demand):>11} | "
        cells = []
        for soc in soc_levels:
            cells.append(f"{grid_map[demand][soc]:>12}")
        print(row_str + " | ".join(cells))
        
    print("="*70)
    
    df = pd.DataFrame(results)
    os.makedirs("results", exist_ok=True)
    df.to_csv("results/operating_envelope.csv", index=False)
    print("\nRaw numerical results saved to results/operating_envelope.csv")

if __name__ == "__main__":
    run_sensitivity()
