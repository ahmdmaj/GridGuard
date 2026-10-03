import json
import os
from scenarios.disasters import DisasterOrchestrator

def main() -> None:
    orchestrator = DisasterOrchestrator()
    
    print("Running solar_scarcity scenario...")
    metrics1 = orchestrator.run_disaster("solar_scarcity")
    
    print("Running generator_failure scenario...")
    metrics2 = orchestrator.run_disaster("generator_failure")
    
    print("Running comms_blackout scenario...")
    metrics3 = orchestrator.run_disaster("comms_blackout")
    
    results = {
        "solar_scarcity": metrics1,
        "generator_failure": metrics2,
        "comms_blackout": metrics3
    }
    
    os.makedirs("data", exist_ok=True)
    with open("data/phase9_results.json", "w") as f:
        json.dump(results, f, indent=4)
        
    print("Disaster scenarios completed successfully! Results saved to data/phase9_results.json.")

if __name__ == "__main__":
    main()
