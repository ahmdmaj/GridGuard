from typing import Optional, Dict, Any, List
from enum import Enum, auto
from simulator.telemetry import TelemetrySnapshot
from digital_twin.state import DigitalTwinState, GridState, SolarState, BatteryState, GeneratorState, LoadState

class TwinEvent(Enum):
    GRID_FAILURE = auto()
    GRID_RESTORED = auto()
    GENERATOR_STARTED = auto()
    GENERATOR_STOPPED = auto()
    BATTERY_LOW = auto()
    FUEL_LOW = auto()

class DigitalTwin:
    def __init__(self) -> None:
        self.state = DigitalTwinState()
        self.history: List[DigitalTwinState] = []
        self.events: List[Dict[str, Any]] = []

    def update(self, telemetry: TelemetrySnapshot) -> None:
        # Event Detection
        timestamp = telemetry["timestamp"]
        
        if self.state.grid.is_available and not telemetry["grid_available"]:
            self.events.append({"timestamp": timestamp, "event": TwinEvent.GRID_FAILURE, "details": "Grid failure detected."})
        if not self.state.grid.is_available and telemetry["grid_available"]:
            self.events.append({"timestamp": timestamp, "event": TwinEvent.GRID_RESTORED, "details": "Grid restored."})
            
        if self.state.generator.power_kw == 0.0 and telemetry["generator_kw"] > 0:
            self.events.append({"timestamp": timestamp, "event": TwinEvent.GENERATOR_STARTED, "details": "Generator started."})
        if self.state.generator.power_kw > 0 and telemetry["generator_kw"] == 0.0:
            self.events.append({"timestamp": timestamp, "event": TwinEvent.GENERATOR_STOPPED, "details": "Generator stopped."})
            
        if self.state.battery.soc >= 25.0 and telemetry["battery_soc"] < 25.0:
            self.events.append({"timestamp": timestamp, "event": TwinEvent.BATTERY_LOW, "details": "Battery SOC dropped below 25%."})
            
        if self.state.generator.fuel_liters >= 15.0 and telemetry["generator_fuel_liters"] < 15.0:
            self.events.append({"timestamp": timestamp, "event": TwinEvent.FUEL_LOW, "details": "Generator fuel dropped below 15L."})

        # State Update
        new_state = DigitalTwinState(
            timestamp=timestamp,
            grid=GridState(
                is_available=telemetry["grid_available"],
                voltage_pu=telemetry["grid_voltage"]
            ),
            solar=SolarState(
                power_kw=telemetry["solar_kw"]
            ),
            battery=BatteryState(
                soc=telemetry["battery_soc"],
                power_kw=telemetry["battery_kw"]
            ),
            generator=GeneratorState(
                power_kw=telemetry["generator_kw"],
                fuel_liters=telemetry["generator_fuel_liters"],
                is_available=telemetry.get("generator_available", True)
            ),
            loads=LoadState(
                critical_kw=telemetry["load_critical_kw"],
                important_kw=telemetry["load_important_kw"],
                flexible_kw=telemetry["load_flexible_kw"]
            )
        )
        self.state = new_state

        # History tracking (optional deep copy might be needed but DigitalTwinState is newly created above)
        self.history.append(self.state)
        if len(self.history) > 100:
            self.history.pop(0)

    def get_current_state(self) -> DigitalTwinState:
        return self.state

