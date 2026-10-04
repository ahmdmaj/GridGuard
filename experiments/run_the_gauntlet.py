import datetime
import sys
import os
import pandas as pd

# Ensure the root project directory is in the Python path
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from physical.plant import PhysicalPlant
from physical.feeder import SagEvent
from controller.engine import DecisionEngine
from forecasting.service import MLForecastService
from metrics.esh import ESHCalculator
from digital_twin.state import DigitalTwinState, GridState, SolarState, BatteryState, GeneratorState, LoadState

def run_gauntlet():
    config = {
        "z_pu": 0.1,
        "p_feeder_rating_kw": 500.0,
        "inverter_rating_kw": 20.0,
        "battery_capacity_kwh": 40.0,
        "battery_max_discharge_kw": 20.0,
        "generator_capacity_kw": 15.0,
        "bg_peak_kw": 300.0,
        "noise_sigma_pu": 0.0,
        "critical_kw": 3.0,
        "important_kw": 2.0,
        "non_essential_kw": 1.0,
        "esh_threshold_hours": 24.0,
        "generator_start_esh_hours": 1.5,
        "shed_flexible_esh": 6.0,
    }
    
    start_time = datetime.datetime(2026, 1, 1, 16, 30, 0)
    plant = PhysicalPlant(config)
    
    # Grid fails at 16:40 (10 mins in)
    sag_start = start_time + datetime.timedelta(minutes=10)
    plant.feeder.add_sag_event(SagEvent(sag_start, 12 * 3600.0, 1.0))
    
    # Initialize GridGuard
    engine = DecisionEngine(config)
    forecast_service = MLForecastService(model_path="ml/models/forecast_model.joblib")
    esh_calc = ESHCalculator(config)
    
    # Set initial state
    plant.battery.current_energy_kwh = 16.0 # 40% SOC
    plant.generator.fuel_liters = 100.0
    
    dt_s = 300.0 # 5 min steps
    current_time = start_time
    
    trace_rows = []
    
    last_gen_run = False
    last_flex_shed = False
    last_imp_shed = False
    
    print("\n" + "="*80)
    print("THE GAUNTLET: INCIDENT NARRATIVE LOG".center(80))
    print("="*80)
    
    next_forecast_time = current_time
    expected_esh = {}
    shadow_esh = {}
    
    for step in range(36): # 3 hours
        hour = current_time.hour + current_time.minute / 60.0
        
        # Dynamic solar (sun sets around 18:00)
        # At 16:30, it's 1.5 hours before sunset. Let's make it physically drop.
        if hour < 18.5 and hour >= 6.0:
            solar_power = max(0.0, 10.0 * (1.0 - abs(hour - 12.0) / 6.5))
        else:
            solar_power = 0.0
        plant.solar.power_kw = solar_power
        
        # At 16:40 (Step 2), Demand spikes!
        if current_time >= sag_start:
            plant.loads.nominal_kw["critical"] = 10.0
            plant.loads.nominal_kw["important"] = 10.0
            plant.loads.nominal_kw["non_essential"] = 25.0
            
        telemetry = {
            "ts": current_time.isoformat() + "Z",
            "v_rms_pu": plant.v_pcc_pu,
            "grid_connected": plant.v_pcc_pu > 0.5,
            "soc": plant.battery.soc,
            "fuel_liters": plant.generator.fuel_liters,
            "gen_available": True
        }
        
        twin_state = DigitalTwinState(
            timestamp=telemetry["ts"],
            grid=GridState(voltage_pu=telemetry["v_rms_pu"], is_available=telemetry["grid_connected"]),
            solar=SolarState(power_kw=solar_power),
            battery=BatteryState(soc=telemetry["soc"]),
            generator=GeneratorState(fuel_liters=telemetry["fuel_liters"], is_available=telemetry["gen_available"], power_kw=(15.0 if plant.generator.is_running else 0.0)),
            loads=LoadState(
                critical_kw=plant.loads.nominal_kw["critical"],
                important_kw=plant.loads.nominal_kw["important"],
                flexible_kw=plant.loads.nominal_kw["non_essential"]
            )
        )
        
        if current_time >= next_forecast_time:
            forecasts = forecast_service.generate_forecast(twin_state, 12 * 12)
            expected_esh = esh_calc.calculate_forecast_esh(twin_state, forecasts, assume_island=False)
            
            # Compute battery_only_esh correctly for the engine
            import copy
            bat_twin = copy.deepcopy(twin_state)
            bat_twin.generator.is_available = False
            shadow_esh = esh_calc.calculate_forecast_esh(bat_twin, forecasts, assume_island=True)
            next_forecast_time += datetime.timedelta(minutes=15)
            
        cmd = engine.evaluate(twin_state, expected_esh, shadow_esh)
        
        # Extract commands
        gen_run = cmd.get("generator_run", False)
        flex_connected = cmd.get("connect_flexible", True)
        imp_connected = cmd.get("connect_important", True)
        reason = cmd.get("decision_reason", "")
        flex_shed = not flex_connected
        imp_shed = not imp_connected
        
        time_str = current_time.strftime("%H:%M")
        
        # Check for state changes to log narrative
        if step == 2:
            print(f"[{time_str}] GRID FAILED. Demand spikes instantly to 45.0 kW.")
            
        if gen_run != last_gen_run or flex_shed != last_flex_shed or imp_shed != last_imp_shed:
            print(f"[{time_str}] ACTION TAKEN: {reason}")
            if flex_shed and not last_flex_shed:
                print(f"[{time_str}] -> Shedding Flexible Load.")
            if imp_shed and not last_imp_shed:
                print(f"[{time_str}] -> Shedding Important Load.")
            if gen_run and not last_gen_run:
                print(f"[{time_str}] -> Starting Generator.")
            
        last_gen_run = gen_run
        last_flex_shed = flex_shed
        last_imp_shed = imp_shed
        
        # Record trace
        trace_rows.append({
            "Timestamp": time_str,
            "Grid_Status": "ONLINE" if telemetry["grid_connected"] else "OFFLINE",
            "Solar_kW": round(solar_power, 2),
            "Demand_kW": round(twin_state.loads.critical_kw + twin_state.loads.important_kw + twin_state.loads.flexible_kw, 2),
            "Battery_SOC": round(telemetry["soc"], 1),
            "ESH": round(shadow_esh.get("critical_only_hours", 0), 2),
            "Generator_Run": gen_run,
            "Flexible_Shed": flex_shed
        })
        
        # Step Physics Plant
        shed_tier = 0
        if flex_shed and imp_shed:
            shed_tier = 2
        elif flex_shed:
            shed_tier = 1
            
        plant_cmd = {
            "inverter_mode": "GRID_PASS" if telemetry["grid_connected"] else "ISLAND",
            "shed_tier": shed_tier,
            "gen_cmd": "START" if gen_run else "STOP"
        }
        
        plant.step(dt_s, current_time, plant_cmd)
        
        current_time += datetime.timedelta(seconds=dt_s)
        
    df = pd.DataFrame(trace_rows)
    os.makedirs("results", exist_ok=True)
    df.to_csv("results/gauntlet_trace.csv", index=False)
    print("\n[END] Gauntlet completed. Trace saved to results/gauntlet_trace.csv")
    print("="*80)

if __name__ == "__main__":
    run_gauntlet()
