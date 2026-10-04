import datetime
import os
import sys
import csv
import pandas as pd

# Ensure the root project directory is in the Python path
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))
from physical.plant import PhysicalPlant
from intelligence.baseline import BaselineController, BaselineHysteresisController
from controller.engine import DecisionEngine
from metrics.esh import ESHCalculator
from digital_twin.state import DigitalTwinState, GridState, SolarState, BatteryState, GeneratorState, LoadState
from forecasting.service import PersistenceForecastService, MLForecastService

def run_evaluation(scenario_name: str, controller_name: str) -> dict:
    config = {
        "z_pu": 0.1,
        "p_feeder_rating_kw": 500.0,
        "inverter_rating_kw": 20.0,
        "battery_capacity_kwh": 40.0,
        "generator_capacity_kw": 15.0,
        "bg_peak_kw": 300.0,
        "noise_sigma_pu": 0.0,
        "reconnect_flexible_esh": 12.0,
        "reconnect_important_esh": 12.0
    }
    
    start_time = datetime.datetime(2026, 1, 1, 12, 0, 0)
    end_time = datetime.datetime(2026, 1, 1, 23, 0, 0)
    
    # Configure scenario overrides
    sags = []
    if scenario_name == "S4_Outage":
        sags = [{"start_hour": 14.0, "duration_hours": 4.0, "depth": 1.0}]
    elif scenario_name == "S8_Sensor_Noise":
        config["noise_sigma_pu"] = 0.05
    elif scenario_name == "S9_Peak_Demand":
        sags = [{"start_hour": 14.0, "duration_hours": 2.0, "depth": 1.0}]
        config["bg_peak_kw"] = 600.0 # Creates peak demand issue
        config["critical_kw"] = 25.0
        config["important_kw"] = 10.0
        config["non_essential_kw"] = 10.0
    elif scenario_name == "S11_Sunset_Outage":
        start_time = datetime.datetime(2026, 1, 1, 15, 0, 0)
        sags = [{"start_hour": 16.0, "duration_hours": 6.0, "depth": 1.0}]

    plant = PhysicalPlant(config)
    from physical.feeder import SagEvent
    
    for sag in sags:
        sag_start = start_time + datetime.timedelta(hours=sag["start_hour"] - 12.0)
        plant.feeder.add_sag_event(SagEvent(sag_start, sag["duration_hours"] * 3600.0, sag["depth"]))
        
    # Init controllers
    if controller_name == "A0_Naive":
        controller = BaselineController()
    elif controller_name == "B1_Hysteresis":
        controller = BaselineHysteresisController()
    else:
        controller = DecisionEngine(config)
        esh_calc = ESHCalculator(config)
        if controller_name == "GridGuard_ML":
            forecast_service = MLForecastService(model_path="ml/models/forecast_model.joblib")
        else:
            forecast_service = PersistenceForecastService()

    dt_s = 300.0 # 5 min steps
    current_time = start_time
    plant.battery.current_energy_kwh = 20.0 # 50% SOC
    initial_fuel = plant.generator.fuel_liters
    
    metrics = {
        "Fuel_L": 0.0,
        "Crit_Unserved": 0.0,
        "Imp_Unserved": 0.0,
        "Flex_Unserved": 0.0
    }
    
    next_forecast_time = current_time
    expected_esh = {}
    shadow_esh = {}
    
    while current_time < end_time:
        hour = current_time.hour + current_time.minute / 60.0
        
        # Sunset logic
        if hour < 19.0 and hour >= 6.0:
            solar_power = max(0.0, 10.0 * (1.0 - abs(hour - 12.0) / 7.0))
        else:
            solar_power = 0.0
        plant.solar.power_kw = solar_power
        
        # Sags/Outages (let plant.step handle voltage physics)
        
        telemetry = {
            "ts": current_time.isoformat() + "Z",
            "v_rms_pu": plant.v_pcc_pu,
            "grid_connected": plant.v_pcc_pu > 0.5, # simplified check
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
        
        if controller_name in ["A0_Naive", "B1_Hysteresis"]:
            time_offset = (current_time - start_time).total_seconds()
            cmd = controller.evaluate(dt_s, time_offset, telemetry)
        else:
            if current_time >= next_forecast_time:
                forecasts = forecast_service.generate_forecast(twin_state, 12 * 12)
                expected_esh = esh_calc.calculate_forecast_esh(twin_state, forecasts, assume_island=False)
                
                # Fix: Compute battery-only ESH by masking the generator
                import copy
                bat_twin = copy.deepcopy(twin_state)
                bat_twin.generator.is_available = False
                shadow_esh = esh_calc.calculate_forecast_esh(bat_twin, forecasts, assume_island=True)
                
                next_forecast_time += datetime.timedelta(minutes=15)
            cmd = controller.evaluate(twin_state, expected_esh, shadow_esh)

        # Before stepping, record what was actually connected
        if type(cmd) == dict:
            flex_connected = cmd.get("connect_flexible", True)
            imp_connected = cmd.get("connect_important", True)
            start_gen = cmd.get("generator_run", False)
            
            # Translate to physical plant format
            shed_tier = 0
            if not flex_connected and not imp_connected:
                shed_tier = 2
            elif not flex_connected:
                shed_tier = 1
                
            cmd["shed_tier"] = shed_tier
            if "generator_run" in cmd:
                cmd["gen_cmd"] = "START" if cmd["generator_run"] else "STOP"
        else:
            flex_connected = True
            imp_connected = True

        res = plant.step(dt_s, current_time, cmd)
        
        # Calculate unserved
        telem = res["plant_telem"]
        
        req_flex = plant.loads.nominal_kw["non_essential"] * (dt_s / 3600.0)
        req_imp = plant.loads.nominal_kw["important"] * (dt_s / 3600.0)
        req_crit = plant.loads.nominal_kw["critical"] * (dt_s / 3600.0)
        
        served_flex = telem["load_flexible_kw"] * (dt_s / 3600.0)
        served_imp = telem["load_important_kw"] * (dt_s / 3600.0)
        served_crit = telem["load_critical_kw"] * (dt_s / 3600.0)
        
        flex_unserved = max(0.0, req_flex - served_flex)
        imp_unserved = max(0.0, req_imp - served_imp)
        crit_unserved = max(0.0, req_crit - served_crit) + (telem["unserved_kw"] * (dt_s / 3600.0))

        metrics["Flex_Unserved"] += flex_unserved
        metrics["Imp_Unserved"] += imp_unserved
        metrics["Crit_Unserved"] += crit_unserved
        
        current_time += datetime.timedelta(seconds=dt_s)
        
    metrics["Fuel_L"] = initial_fuel - plant.generator.fuel_liters
    return metrics

def main():
    scenarios = ["S4_Outage", "S8_Sensor_Noise", "S9_Peak_Demand", "S11_Sunset_Outage"]
    controllers = ["A0_Naive", "B1_Hysteresis", "GridGuard_Persistence", "GridGuard_ML"]
    
    results = []
    
    print("Running Final Competition Evaluation Matrix...\n")
    
    for scenario in scenarios:
        for controller in controllers:
            print(f"Evaluating {controller} in {scenario}...")
            metrics = run_evaluation(scenario, controller)
            results.append({
                "Scenario": scenario,
                "Controller": controller,
                "Fuel_L": round(metrics["Fuel_L"], 2),
                "Crit_Unserved": round(metrics["Crit_Unserved"], 2),
                "Imp_Unserved": round(metrics["Imp_Unserved"], 2),
                "Flex_Unserved": round(metrics["Flex_Unserved"], 2)
            })
            
    df = pd.DataFrame(results)
    
    os.makedirs("results", exist_ok=True)
    df.to_csv("results/final_competition_matrix.csv", index=False)
    
    print("\n" + "="*80)
    print("FINAL COMPETITION MATRIX".center(80))
    print("="*80)
    print(df.to_string(index=False))
    print("="*80)
    print("\nResults exported to results/final_competition_matrix.csv")

if __name__ == "__main__":
    main()
