import datetime
import os
import csv
from physical.plant import PhysicalPlant
from controller.engine import DecisionEngine
from metrics.esh import ESHCalculator
from digital_twin.state import DigitalTwinState, GridState, SolarState, BatteryState, GeneratorState, LoadState
from forecasting.service import PersistenceForecastService, MLForecastService

def run_validation(forecast_service_name: str) -> dict:
    config = {
        "z_pu": 0.1,
        "p_feeder_rating_kw": 500.0,
        "inverter_rating_kw": 20.0,
        "battery_capacity_kwh": 40.0,
        "generator_capacity_kw": 15.0,
        "bg_peak_kw": 400.0,
        "noise_sigma_pu": 0.0,
    }
    
    plant = PhysicalPlant(config)
    controller = DecisionEngine(config)
    esh_calc = ESHCalculator(config)
    
    if forecast_service_name == "ML":
        forecast_service = MLForecastService(model_path="ml/models/forecast_model.joblib")
    else:
        forecast_service = PersistenceForecastService()
        
    current_time = datetime.datetime(2026, 1, 1, 16, 0, 0)
    dt_s = 300.0 # 5 minute steps
    end_time = datetime.datetime(2026, 1, 1, 23, 0, 0) # run until 11 PM
    
    # Starting conditions
    plant.battery.current_energy_kwh = 20.0 # 50% SOC (40 kWh capacity)
    initial_fuel = plant.generator.fuel_liters
    
    metrics = {
        "esh_at_outage_start": 0.0,
        "unserved_energy_kwh": 0.0,
        "generator_fuel_l_used": 0.0,
    }
    
    step_num = 0
    next_forecast_time = current_time
    
    while current_time < end_time:
        # Enforce physical sunset (16:00 to 19:00 drops to 0)
        hour = current_time.hour + current_time.minute / 60.0
        if hour < 19.0:
            # 16:00 is hour 16.0
            solar_power = max(0.0, 10.0 * (19.0 - hour) / 3.0)
        else:
            solar_power = 0.0
            
        plant.solar.power_kw = solar_power # direct override
        
        # Grid outage
        if 16.0 + 25.0/60.0 <= hour < 22.0:
            is_grid_available = False
            # Physical voltage drop simulated if needed, or we just rely on grid_connected=False
            plant.v_pcc_pu = 0.0
        else:
            is_grid_available = True
            plant.v_pcc_pu = 1.0
            
        telemetry = {
            "ts": current_time.isoformat() + "Z",
            "v_rms_pu": plant.v_pcc_pu,
            "grid_connected": is_grid_available,
            "soc": plant.battery.soc,
            "fuel_liters": plant.generator.fuel_liters,
            "gen_available": True
        }
        
        # Build twin state
        twin_state = DigitalTwinState(
            timestamp=telemetry["ts"],
            grid=GridState(voltage_pu=telemetry["v_rms_pu"], is_available=telemetry["grid_connected"]),
            solar=SolarState(power_kw=solar_power),
            battery=BatteryState(soc=telemetry["soc"]),
            generator=GeneratorState(fuel_liters=telemetry["fuel_liters"], is_available=telemetry["gen_available"], power_kw=(15.0 if plant.generator.is_running else 0.0)),
            loads=LoadState(critical_kw=4.0, important_kw=3.0, flexible_kw=2.0)
        )
        
        # Generate forecast every step for simplicity, or 15 mins. Let's do 15 mins.
        if current_time >= next_forecast_time:
            forecasts = forecast_service.generate_forecast(twin_state, 12 * 12) # 12 hours
            expected_esh = esh_calc.calculate_forecast_esh(twin_state, forecasts, assume_island=False)
            shadow_esh = esh_calc.calculate_forecast_esh(twin_state, forecasts, assume_island=True)
            next_forecast_time += datetime.timedelta(minutes=15)
            
        # Capture ESH at Step 5 (16:25)
        if step_num == 5:
            metrics["esh_at_outage_start"] = shadow_esh.get("critical_only_hours", 0.0)
            
        cmd = controller.evaluate(twin_state, expected_esh, shadow_esh)
        
        # Apply command to plant
        res = plant.step(dt_s, current_time, cmd)
        
        metrics["unserved_energy_kwh"] += (res["plant_telem"]["unserved_kw"] * (dt_s / 3600.0))
        
        current_time += datetime.timedelta(seconds=dt_s)
        step_num += 1
        
    metrics["generator_fuel_l_used"] = initial_fuel - plant.generator.fuel_liters
    return metrics

def main():
    print("Running ML Validation Comparison...\n")
    
    print("1. Testing Persistence Forecast...")
    metrics_persistence = run_validation("Persistence")
    
    print("2. Testing ML Forecast...")
    metrics_ml = run_validation("ML")
    
    print("\n--- RESULTS COMPARISON ---")
    print(f"{'Metric':<25} | {'Persistence':<15} | {'ML Forecast':<15}")
    print("-" * 60)
    print(f"{'ESH at Outage (h)':<25} | {metrics_persistence['esh_at_outage_start']:<15.2f} | {metrics_ml['esh_at_outage_start']:<15.2f}")
    print(f"{'Fuel Consumed (L)':<25} | {metrics_persistence['generator_fuel_l_used']:<15.2f} | {metrics_ml['generator_fuel_l_used']:<15.2f}")
    print(f"{'Unserved Energy (kWh)':<25} | {metrics_persistence['unserved_energy_kwh']:<15.2f} | {metrics_ml['unserved_energy_kwh']:<15.2f}")
    
    os.makedirs("results", exist_ok=True)
    with open("results/ml_validation_comparison.csv", "w", newline="") as f:
        writer = csv.writer(f)
        writer.writerow(["Forecast_Type", "ESH_at_Outage_h", "Fuel_Consumed_L", "Unserved_Energy_kWh"])
        writer.writerow(["Persistence", metrics_persistence["esh_at_outage_start"], metrics_persistence["generator_fuel_l_used"], metrics_persistence["unserved_energy_kwh"]])
        writer.writerow(["ML", metrics_ml["esh_at_outage_start"], metrics_ml["generator_fuel_l_used"], metrics_ml["unserved_energy_kwh"]])
        
if __name__ == "__main__":
    main()
