import json
import os
from scenarios.experiment import ExperimentRunner

def main() -> None:
    runner = ExperimentRunner()
    
    print("Running Baseline scenario...")
    baseline_metrics, _ = runner.run_scenario("baseline")
    
    print("Running GridGuard scenario...")
    gridguard_metrics, _ = runner.run_scenario("gridguard")
    
    comparison = {
        "Baseline": baseline_metrics,
        "GridGuard": gridguard_metrics
    }
    
    os.makedirs("data", exist_ok=True)
    with open("data/phase7_results.json", "w") as f:
        json.dump(comparison, f, indent=4)
        
    print("Experiment completed successfully! Results saved to data/phase7_results.json.")

if __name__ == "__main__":
    main()
