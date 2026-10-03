import os
import csv
from scenarios.experiment import ExperimentRunner

def main() -> None:
    starting_energies = [10.0, 15.0, 20.0, 25.0, 30.0]
    
    os.makedirs("data", exist_ok=True)
    with open("data/sensitivity_results.csv", "w", newline='') as f:
        writer = csv.writer(f)
        writer.writerow(["Starting_Battery_kWh", "Baseline_Unserved", "Baseline_Fuel", "GridGuard_Unserved", "GridGuard_Fuel"])
        
        for energy in starting_energies:
            runner_baseline = ExperimentRunner(start_soc_kwh=energy)
            baseline_metrics, _ = runner_baseline.run_scenario("baseline")
            
            runner_gridguard = ExperimentRunner(start_soc_kwh=energy)
            gridguard_metrics, _ = runner_gridguard.run_scenario("gridguard")
            
            writer.writerow([
                energy,
                baseline_metrics["total_unserved_energy_kwh"],
                baseline_metrics["fuel_consumed_liters"],
                gridguard_metrics["total_unserved_energy_kwh"],
                gridguard_metrics["fuel_consumed_liters"]
            ])
            print(f"Completed energy level {energy} kWh")
            
if __name__ == "__main__":
    main()
