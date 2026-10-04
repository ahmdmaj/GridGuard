# GridGuard

GridGuard is an intelligent edge controller and Digital Twin simulator for high-reliability microgrids. It prevents critical power failures during severe grid anomalies by orchestrating batteries, generators, and load shedding based on physics-based simulations and machine learning forecasts.

## Project Structure

The repository is organized into the following core modules:

* `physical/`: Physics-based models of the microgrid components (battery, generator, inverter, feeder, loads, protection relays).
* `intelligence/`: The decision engine, baseline controllers, Energy Survival Horizon (ESH) calculator, and forecasting services.
* `transport/`: Telemetry and communications layer, including MQTT broker abstractions.
* `experiments/`: Experiment runner scripts for various scenarios, ablation studies, and sensitivity analysis.
* `ml/`: Machine learning pipeline, feature engineering, and model training.

## Status

| Feature | Done and tested | Implemented, not yet validated | Planned |
| :--- | :--- | :--- | :--- |
| **ML forecasting** | | Models trained on synthetic load and voltage data plus Open-Meteo weather for one location. The inference path currently uses placeholder weather and lag inputs; the ablation shows no difference between rule-based and ML variants. | |
| **MQTT transport** | | Code present; not yet run against a broker. | |
| **Monte Carlo and sensitivity** | | | Planned; earlier results withdrawn. |

## Running GridGuard

The following experiments and legacy scripts are currently functional:

### Modern Experiments
* `python experiments/run_scenarios.py`: Evaluates GridGuard and the baseline controller against Phase 1 anomaly scenarios (S1-S8).
* `python experiments/run_ablation.py`: Evaluates forecast performance impact in a sag-to-outage scenario.

### Legacy Scripts
These scripts use older simulation wrappers but remain functional for demonstration purposes:
* `python run_live.py`: Runs a continuous, realtime visualization of the Digital Twin in the terminal.
* `python run_experiment.py`: Runs a basic comparative trial.
* `python run_disasters.py`: Runs a trial over edge-case disasters (solar scarcity, generator failure, comms blackout).

## Installation

Ensure you are using Python 3.10 (as used in Docker and CI) or the local virtual environment (Python 3.14.5 for local experiments).

```bash
python -m venv venv
# Windows
.\venv\Scripts\activate
# Linux/Mac
source venv/bin/activate

pip install -r requirements.txt
```
