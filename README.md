# GridGuard: Autonomous Energy Resilience Engine

## Overview
GridGuard is an autonomous energy resilience system designed to manage building energy during catastrophic grid failures. Instead of relying on static, reactive thresholds, GridGuard utilizes forecast-aware **Energy Survival Horizons (ESH)** to dynamically shed non-essential loads, optimizing battery life and generator fuel consumption to ensure critical infrastructure survives prolonged outages.

## Core Architecture (The "Air Gap")
A fundamental design constraint of GridGuard is the strict decoupling of the Intelligence Layer from the Physical Layer. 

- **Physical Layer**: The simulated `PhysicalPlant` (Grid, Solar, Battery, Generator, and Load).
- **Intelligence Layer**: The `DecisionEngine`, `DigitalTwin`, `ForecastService`, and `ESHCalculator`.

These two layers operate as independent IoT nodes. They communicate *exclusively* via a Mock MQTT Broker using serialized JSON payloads (`TOPIC_TELEMETRY` and `TOPIC_COMMAND`). The Intelligence Layer can only see what the physical sensors broadcast, and the Physical Layer only reacts to validated command structures. This mathematical "Air Gap" ensures the AI cannot cheat by reading physical memory or private simulation variables, proving the system is fully networked and deployment-ready for the real world.

## The Engine: Energy Survival Horizon (ESH)
GridGuard's decision-making is powered by the Energy Survival Horizon (ESH) algorithm. 

Instead of waiting for the battery to hit a rigid panic threshold (e.g., 20% SOC), the ESH calculator steps forward in time through forecasted weather generation and load demands. It dynamically simulates the depletion curve across three load tiers (Critical Only, Critical + Important, All Loads) to find the exact fractional timestep of battery death. 

By constantly recalculating this horizon, GridGuard proactively sheds lower-tier loads when the future looks bleak, and uses a stateful hysteresis loop to safely cycle the generator—preserving critical fuel reserves while keeping the building alive.

## Project Status

| Feature | Status |
|---|---|
| Physical Simulation (Feeder, Loads, Inverter) | **Done and tested** |
| Energy Survival Horizon (ESH) & Decision Engine | **Done and tested** |
| Scenario Automation (S1-S8) & Monte Carlo | **Implemented but not yet validated** |
| ML Forecasting | **Planned** (Pipeline implemented; trained models pending; system currently uses rule-based forecaster) |

## How to Run

GridGuard includes a comprehensive suite of execution scripts and visualizers. From the root directory, use the following commands to evaluate the system:

### 1. Real-Time ASCII Visualizer
Watch the Digital Twin, Physical Plant, and AI Controller interact frame-by-frame during a simulated grid failure.
```bash
python run_live.py
```

### 2. Head-to-Head Experiment
Run a 12-hour stress test comparing GridGuard's AI against a standard, fixed-rule Baseline Controller.
```bash
python run_experiment.py
```

### 3. Fault & Disaster Scenarios
Subject the architecture to severe physical and network disasters (e.g., generator failure, prolonged solar scarcity, and MQTT comms blackouts).
```bash
python run_disasters.py
```

### 4. ESH Mathematical Validation
Run a strict battery depletion test to mathematically prove the accuracy of the ESH predictions and evaluate GridGuard's hardware sensitivity.
```bash
python validation/esh_validator.py
python validation/sensitivity.py
```

### 5. Full Test Suite
Execute the comprehensive suite of unit and integration tests verifying all mathematical models, nodes, and isolated logic.
```bash
python -m pytest -v
```

## Limitations and Risks
- **Phase 1 Limitations**: The current implementation utilizes a simplified explicit integration step for resolving voltage/power circular dependencies (using the previous step's import power to calculate current voltage). For extreme impedance scenarios, this could introduce minor numerical instability.
- **Idealised Sensors**: Telemetry currently assumes 100% accurate measurement (aside from explicitly injected noise). Sensor drift and calibration errors are not modeled.
- **Rule-based Forecasts**: The current forecasting logic is simple and rule-based. Phase 2 ML integrations will introduce probabilistic forecast errors which the system must be tuned to handle gracefully.
- **Hardware Limitations**: Battery degradation, thermal derating, and nonlinear efficiency curves are currently omitted to simplify the core ESH logic.
