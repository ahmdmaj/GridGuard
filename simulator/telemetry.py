from typing import TypedDict

class TelemetrySnapshot(TypedDict):
    timestamp: str
    grid_available: bool
    grid_voltage: float
    solar_kw: float
    battery_soc: float
    battery_kw: float
    generator_kw: float
    generator_fuel_liters: float
    generator_available: bool
    load_critical_kw: float
    load_important_kw: float
    load_flexible_kw: float
    unserved_kw: float
