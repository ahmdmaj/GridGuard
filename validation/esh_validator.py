import os
import csv
from simulator.runner import SimulationRunner
from digital_twin.twin import DigitalTwin
from metrics.esh import ESHCalculator
from simulator.constants import LoadCategory

def main() -> None:
    runner = SimulationRunner()
    twin = DigitalTwin()
    esh_calc = ESHCalculator()

    # Force conditions
    runner.plant.grid.fail()
    runner.plant.generator.set_availability(False)
    runner.plant.solar.set_availability(0.0)

    # Set battery state
    runner.plant.battery.capacity_kwh = 40.0
    runner.plant.battery.current_energy_kwh = 40.0

    # Take one telemetry snapshot
    telemetry = runner.plant.get_telemetry(runner.current_time)
    twin.update(telemetry)
    
    # Calculate Instantaneous ESH
    esh = esh_calc.calculate_instantaneous_esh(twin.get_current_state())
    predicted_critical_hours = esh["critical_only_hours"]
    
    # Run a simulation loop disconnecting Important and Flexible
    runner.plant.load.set_connection(LoadCategory.CRITICAL, True)
    runner.plant.load.set_connection(LoadCategory.IMPORTANT, False)
    runner.plant.load.set_connection(LoadCategory.FLEXIBLE, False)
    
    steps = 0
    while True:
        active_load = runner.plant.load.get_total_demand_kw()
        runner.run_step(battery_command_kw=active_load)
        steps += 1
        
        telemetry = runner.plant.get_telemetry(runner.current_time)
        unserved = telemetry["unserved_kw"]
        
        if unserved > 0:
            break
            
    actual_critical_hours = steps * (5.0 / 60.0)
    error_margin = abs(predicted_critical_hours - actual_critical_hours)
    
    print(f"Predicted Critical Hours: {predicted_critical_hours:.2f}")
    print(f"Actual Critical Hours: {actual_critical_hours:.2f}")
    print(f"Error Margin: {error_margin:.2f}")
    
    os.makedirs("data", exist_ok=True)
    with open("data/esh_validation.csv", "w", newline='') as f:
        writer = csv.writer(f)
        writer.writerow(["Test_Name", "Predicted_Hours", "Actual_Hours", "Error_Margin"])
        writer.writerow(["Battery_Depletion_Test", predicted_critical_hours, actual_critical_hours, error_margin])

if __name__ == "__main__":
    main()
