# GridGuard

GridGuard is an intelligent edge controller and Digital Twin simulator for high-reliability microgrids. It prevents critical power failures during severe grid anomalies by orchestrating batteries, generators, and load shedding based on physics-based simulations and machine learning forecasts.

## Project Structure

The repository is organized into the following core modules:

* `physical/`: Physics-based models of the microgrid components (battery, generator, inverter, feeder, loads, protection relays).
* `intelligence/`: The decision engine, baseline controllers, Energy Survival Horizon (ESH) calculator, and forecasting services.
* `experiments/`: Experiment runner scripts for various scenarios, ablation studies, and sensitivity analysis.
* `ml/`: Machine learning pipeline, feature engineering, and model training.

## Running GridGuard

To evaluate GridGuard, run the final competition matrix. This is the crown jewel of the project and pits four controllers against four defining scenarios that prove our core engineering claims.

```bash
python experiments/run_final_evaluation.py
```

### Architectural Pillars Proven by the Matrix:
1. **Hysteresis (vs A0/B1):** Avoids thrashing and saves fuel during noisy grid voltage conditions (`S8_Sensor_Noise`).
2. **Instantaneous Feasibility:** Protects critical loads during peak demand spikes when physical power is limited (`S9_Peak_Demand`).
3. **ML Forecasting:** Grounds the Energy Survival Horizon (ESH) in realistic temporal weather patterns, shedding flexible loads intelligently before sunset (`S11_Sunset_Outage`).

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
