# GridGuard: Technical Progress Report (IoTrix 2.0 Semi-Finals)

## 1. Architecture & Core Simulation Engine (Completed)
We have successfully engineered a high-fidelity, object-oriented microgrid physics simulator in Python. The simulator operates on a tick-based state machine, calculating continuous power flows, ZIP load models (constant impedance/current/power), and dynamic feeder voltage drops. 
- **Physical Plant Models:** Built independent modules for the Inverter (Static Transfer Switch), Battery Storage (charging/discharging boundaries), Solar PV, and emergency Diesel Generators.
- **Local Protection Relays:** Implemented hardware-level fail-safes that autonomously island the microgrid (0 ms dropout time simulation) when grid voltage drops below 0.88 pu or MQTT communication is lost.

## 2. Machine Learning Forecasting Integration (Completed)
To move beyond reactive logic, we developed a `MLForecastService` powered by a Random Forest Regressor (Scikit-Learn).
- **Data Engineering:** Trained on diurnal datasets mapping hour-of-day and weather scenarios to expected solar irradiance and building demand.
- **Digital Twin Sync:** The model reads live telemetry from the physical plant and generates a predictive 12-hour forward-looking tensor (in 5-minute intervals) for solar generation and segmented load tiers (Critical, Important, Flexible).

## 3. Autonomous AI Decision Engine (Completed)
We developed the core intelligence of GridGuard: The Expected Survival Hours (ESH) Calculator.
- **Look-ahead Logic:** At every tick, the AI evaluates the ML forecast against the current Battery SOC to calculate exactly how many hours the microgrid can survive off-grid.
- **Dynamic Load Shedding:** If the calculated ESH drops below critical thresholds, the engine autonomously sheds Flexible loads, then Important loads, to extend battery life.
- **Generator Orchestration:** If survival time is still insufficient, the AI seamlessly starts the emergency diesel generator, calculates fuel burn rate, and stops it once the battery safely recharges.

## 4. Live Interactive Digital Twin Dashboard (Completed)
We built a real-time, tick-based Streamlit dashboard that acts as our IoT Control Center.
- **State Machine Loop:** The UI is completely decoupled from the physics clock, plotting time-series DataFrames continuously without blocking the execution thread.
- **Chaos Engineering Controls:** We successfully implemented live parameter injection. Judges/users can dynamically toggle Grid Outages, drag Voltage Sag sliders, or force Day/Night cycles via the UI. These overrides instantly inject into the physical memory, and the AI visibly reacts frame-by-frame on the live charts, proving the system's real-time adaptability.

## 5. Next Steps (Final Optimization Phase)
- Implement cloud-based MQTT broker connections to allow remote hardware to receive the AI's shed commands.
- Containerize the architecture (Docker) for streamlined deployment.
