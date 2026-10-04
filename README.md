# GridGuard

GridGuard is an intelligent edge controller and Digital Twin simulator for high-reliability microgrids. It prevents critical power failures during severe grid anomalies by orchestrating batteries, generators, and load shedding based on physics-based simulations and machine learning forecasts.

## Project Structure

The repository is organized into the following core modules:

* `physical/`: Physics-based models of the microgrid components (battery, generator, inverter, feeder, loads, protection relays).
* `intelligence/`: The decision engine, baseline controllers, Energy Survival Horizon (ESH) calculator, and forecasting services.
* `experiments/`: Experiment runner scripts for various scenarios, ablation studies, and sensitivity analysis.
* `ml/`: Machine learning pipeline, feature engineering, and model training.

## The Predictive Advantage (Why ML Matters)

GridGuard does not operate on naive, momentary snapshots. In our operating envelope sweep, the system correctly degraded a 100% charged battery powering a tiny 4 kW load. Why? Because the Random Forest model wasn't fooled by the momentarily low spike. It knew from its historical training data that the *average, realistic* night-time demand for the building is actually around 9.0 kW. By forecasting the true 9.0 kW baseline over the night, it correctly calculated a true Energy Survival Horizon (ESH) of 3.55 hours (crossing the 6.0-hour safety threshold). The AI model actively makes superior physical decisions, degrading the system safely and predictably before catastrophic failure occurs.

## Running GridGuard

The following four execution scripts form the final competition submission:

1. **The Matrix:** `python experiments/run_final_evaluation.py`
   Pits four controllers against four defining scenarios that prove our core engineering claims.
2. **The ML Proof:** `python experiments/run_forecast_benchmark.py`
   Proves the Random Forest model outperforms Persistence/Rule-Based forecasts on unseen data, altering life-saving decision logic.
3. **The Signature Scenario:** `python experiments/run_the_gauntlet.py`
   A time-stamped incident report proving GridGuard can simultaneously balance instantaneous power limits, predict solar collapse, and protect critical voltage.
4. **The Operating Envelope:** `python experiments/run_sensitivity_analysis.py`
   A 2D ASCII heatmap sweep proving GridGuard mathematically degrades gracefully across extreme physical boundaries before failing catastrophically.

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
