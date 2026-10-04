# Validation and Pre-registered Expectations

## Pre-registered Expectations
- B1 is expected to be about equal to GridGuard on S1, S2, S3, S5, S7 and S8.
- GridGuard's advantage is expected to appear only in outage (S4) and forecast (S6) scenarios.

## Pre-peak Charging Assumption
- We assume the pre-peak charging starts at 17:00 and ends at 18:30. The battery can charge at `charge_limit_kw` = 5.0kW for 1.5 hours, providing an extra 7.5 kWh (approx 18.75% SOC). The target is 90.0%. This is physically achievable under normal grid conditions as long as the initial SOC is not below ~71%.

## ESH Report (shadow_esh / battery_only_esh)
The `calculate_forecast_esh` function when run with `assume_island=True` DOES count generator power and fuel, because it reads `gen_available` and `fuel_liters` from the telemetry. 

## Deviations from Phase D & Phase G Design Docs
1. Phase D specified charging in `SUPPORT` mode for pre-peak, but this causes thrashing. The code was changed to charge in `GRID_PASS` (NORMAL) instead.
2. Phase D specified a shadow ESH that is strictly "battery-only". However, the implementation currently uses `assume_island=True` which still relies on the generator if `gen_available` is True in telemetry.
3. Phase G specified the baseline controller charging the battery at a hard-coded `-20.0kW`. The implementation uses `GRID_PASS` mode which inherently charges the battery up to the `charge_limit_kw` (controlled by `plant.py`), requiring no explicit battery kW command from the baseline controller.
