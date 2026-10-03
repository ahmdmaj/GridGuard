# GridGuard Engineering Conventions

These rules strictly govern the GridGuard simulation to ensure consistency across the physical model and the digital twin.

## 1. Units
- **Power:** ALWAYS in Kilowatts (kW).
- **Energy:** ALWAYS in Kilowatt-hours (kWh).
- **Voltage:** in Volts (V).

## 2. Timestep
- **Standard Simulation Timestep:** 5 minutes.

## 3. Power vs. Energy Math
- Energy transfer per timestep is calculated as:
  `Energy (kWh) = Power (kW) * (timestep_minutes / 60)`

## 4. Sign Convention
- **Generation / Supply:** Positive (+)
- **Load / Consumption:** Negative (-)
- **Battery:** Charging is negative (-) from the bus perspective; Discharging is positive (+).

## 5. Timestamps
- All telemetry timestamps must strictly use **ISO 8601 format** (e.g., `YYYY-MM-DDTHH:MM:SSZ`).

## 6. Code Style
- **Variables / Functions:** `snake_case`
- **Classes:** `PascalCase`
- **Constants:** `UPPER_CASE`
- **Logging:** Use the standard Python `logging` module for all system outputs.
