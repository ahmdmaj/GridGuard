# GridGuard Progress Sheet

## 1. Problem
During evening peak demand (18:30-22:30), many Sri Lankan distribution feeders experience sustained under-voltage. Equipment draws more current at low voltage, worsening the sag. Hospitals need a stable supply voltage during these periods and during full outages.

## 2. Proposed Solution
GridGuard is a supervisory energy-management system for a critical facility with grid, solar, battery, and generator. It forecasts the facility's energy balance and grid quality, decides when to support the critical bus from the battery, which loads to shed, and when to start the generator, while protecting critical load as a hard constraint.

## 3. Architecture
- **Physical Layer**: Simulated Grid feeder, solar, battery, inverter/STS, generator, load tiers.
- **Intelligence Layer**: Decision Engine, Digital Twin, Forecast Service, and ESH Calculator.
- **Communication**: Strict separation via MQTT Broker (mock or Mosquitto) to ensure IoT deployability.

## 4. Current Progress
- **Physical Plant & Modes (SUPPORT, ISLAND)**: `python run_live.py`
- **Air-gap constraint validation**: `pytest tests/test_air_gap.py`
- **Ablation baseline comparison**: `python experiments/run_ablation.py`
- **Monte Carlo validation**: `python experiments/run_montecarlo.py`

## 5. Technology Stack
Python 3.10+, Pandas, Pytest. Eclipse Mosquitto (MQTT). Streamlit for dashboarding.

## 6. Testing
- Over 120 automated tests validating logic, ESH bounds, and deterministic physical simulation.
- `make test` executes the complete suite.

## 7. Limitations
- Single lumped-feeder approximation.
- ML forecasting pipeline is implemented but awaiting integration with real feeder data (currently using rule-based).
- Hardware thermal derating and nonlinear battery efficiency curves omitted.

## 8. Next Step
- Finalizing Monte Carlo confidence intervals and sensitivity analysis.
- Retraining ML models on real voltage/weather data.
