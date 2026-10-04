from dataclasses import dataclass
from typing import Optional

@dataclass
class GridState:
    voltage_pu: float = 1.0
    is_available: bool = True

@dataclass
class SolarState:
    power_kw: float = 0.0

@dataclass
class BatteryState:
    soc: float = 100.0
    power_kw: float = 0.0

@dataclass
class GeneratorState:
    fuel_liters: float = 100.0
    power_kw: float = 0.0
    is_available: bool = True

@dataclass
class LoadState:
    critical_kw: float = 0.0
    important_kw: float = 0.0
    flexible_kw: float = 0.0

@dataclass
class DigitalTwinState:
    timestamp: str = ""
    grid: GridState = None
    solar: SolarState = None
    battery: BatteryState = None
    generator: GeneratorState = None
    loads: LoadState = None
    network_connected: bool = True

    def __post_init__(self):
        if self.grid is None:
            self.grid = GridState()
        if self.solar is None:
            self.solar = SolarState()
        if self.battery is None:
            self.battery = BatteryState()
        if self.generator is None:
            self.generator = GeneratorState()
        if self.loads is None:
            self.loads = LoadState()
