# GridGuard Progress Sheet

## Phase 0: Housekeeping
- [x] T0.1 Tag current state v1.0-semifinal
- [x] T0.2 Write docs/progress_sheet.md
- [x] T0.3 Add air-gap test (`tests/test_air_gap.py`)
- [ ] T0.4 Export architecture diagram
- [ ] T0.5 Update README: add Limitations and risks

## Mapping Old Code to Redesign Locations
| Legacy File | New Location | Description |
| ----------- | ------------ | ----------- |
| `simulator/grid.py` | `physical/feeder.py` | Added impedance and background load modelling. |
| `simulator/load.py` | `physical/loads.py` | Added ZIP modeling for voltage-dependent power. |
| `simulator/plant.py` | `physical/plant.py`, `physical/inverter_sts.py`, `physical/local_protection.py` | Plant separated into gateway/switch (STS), orchestrator (plant), and safety relay (local_protection). |
| `simulator/telemetry.py` | `physical/pq_node.py` | Separated out IoT sensor packet generation. |
| `controller/engine.py` | `intelligence/decision_engine.py` | Moved out of rigid binary to multi-state voltage-aware engine. |
| `controller/baseline.py`| `intelligence/baseline.py` | Legacy UPS logic moved to intelligence layer. |
| `metrics/esh.py` | `intelligence/esh.py` | Moved and upgraded to handle Shadow Twin worst-case and probabilistic forecasts. |

## Phase 1: Sri Lankan Voltage Context & ESH Fix
- [x] T1.1: Sri Lankan Grid Feeder Model (`physical/feeder.py`)
- [x] T1.2: ZIP Loads (`physical/loads.py`)
- [x] T1.3: Inverter & STS (`physical/inverter_sts.py`)
- [x] T1.4: PQ Node (`physical/pq_node.py`)
- [x] T1.5: Local Protection (`physical/local_protection.py`)
- [x] T1.6: Decision Engine (`intelligence/decision_engine.py`)
- [x] T1.7: Voltage-aware ESH (`intelligence/esh.py`)
- [x] T1.8: Pre-peak Charging (`intelligence/decision_engine.py`)
- [x] T1.9: Dashboard (`dashboard/app.py`)
- [x] Scenarios & Experiments (`experiments/run_scenarios.py`)

## Phase 2: ML Forecasting (TODO)
- [ ] T2.1-T2.8

## Phase 3: Hardware In Loop (TODO)
- [ ] T3.1-T3.4
