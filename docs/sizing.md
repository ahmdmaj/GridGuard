# Sizing and Economics Note

This note outlines a basic sizing methodology for a simulated healthcare facility. 

## Assumptions
* **Site Type:** Small Rural Clinic
* **Critical Load (Life Support, ER):** 4.0 kW
* **Important Load (Lighting, IT):** 3.0 kW
* **Flexible Load (HVAC, non-critical):** 2.0 kW
* **Total Peak Demand:** 9.0 kW

## Component Sizing

### 1. Inverter Rating
The inverter must be capable of carrying the entire load in `GRID_PASS` and `SUPPORT` modes, plus handling surge currents.
* Base demand: 9.0 kW
* Safety factor: 2.2x (for motor starting / compressor surges)
* **Required Inverter:** 20 kW

### 2. Battery Sizing
The battery must sustain the critical and important loads during a 4-hour evening peak sag/outage window without forcing a generator start.
* Target ESH: 4.0 hours for Critical (4kW) + Important (3kW) = 7.0 kW load
* Total Energy Required = 7.0 kW * 4.0 h = 28.0 kWh
* Accounting for minimum SOC (20%) and discharge efficiency (95%):
* `Total Capacity = (28.0 / 0.95) / (1.0 - 0.2) = 36.8 kWh`
* **Recommended Battery:** 40 kWh (LFP)

### 3. Generator Sizing
The generator is a backup to the battery for extended, multi-day outages. It only needs to carry the critical load while slowly recharging the battery.
* Critical Load: 4.0 kW
* Battery Charge headroom: 10.0 kW
* **Recommended Generator:** 15 kW Diesel

## Scaling to Multiple Sites
GridGuard's air-gapped architecture scales linearly. Each site requires its own local `PhysicalPlant`, `LocalProtection`, and `PowerQualityNode` running on edge hardware (e.g., an ESP32 or industrial PLC). A central cloud or on-prem server runs the `DecisionEngine` and `ForecastService`, communicating with sites via secured MQTT topics (e.g., `site_01/telemetry/grid_pq`).
