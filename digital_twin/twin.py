from typing import Optional, Dict, Any, List
from enum import Enum, auto
from simulator.telemetry import TelemetrySnapshot

class TwinEvent(Enum):
    GRID_FAILURE = auto()
    GRID_RESTORED = auto()
    GENERATOR_STARTED = auto()
    GENERATOR_STOPPED = auto()
    BATTERY_LOW = auto()
    FUEL_LOW = auto()

class DigitalTwin:
    def __init__(self) -> None:
        self.last_update_time: Optional[str] = None
        self.grid_state: Dict[str, Any] = {"is_available": False, "voltage": 0.0}
        self.solar_state: Dict[str, Any] = {"generation_kw": 0.0}
        self.battery_state: Dict[str, Any] = {"soc": 0.0, "power_kw": 0.0}
        self.generator_state: Dict[str, Any] = {"power_kw": 0.0, "fuel_liters": 0.0}
        self.load_state: Dict[str, Any] = {
            "critical_kw": 0.0,
            "important_kw": 0.0,
            "flexible_kw": 0.0,
            "unserved_kw": 0.0
        }
        self.history: List[Dict[str, Any]] = []
        self.events: List[Dict[str, Any]] = []

    def update(self, telemetry: TelemetrySnapshot) -> None:
        # Event Detection
        timestamp = telemetry["timestamp"]
        
        if self.grid_state["is_available"] and not telemetry["grid_available"]:
            self.events.append({"timestamp": timestamp, "event": TwinEvent.GRID_FAILURE, "details": "Grid failure detected."})
        if not self.grid_state["is_available"] and telemetry["grid_available"]:
            self.events.append({"timestamp": timestamp, "event": TwinEvent.GRID_RESTORED, "details": "Grid restored."})
            
        if self.generator_state["power_kw"] == 0.0 and telemetry["generator_kw"] > 0:
            self.events.append({"timestamp": timestamp, "event": TwinEvent.GENERATOR_STARTED, "details": "Generator started."})
        if self.generator_state["power_kw"] > 0 and telemetry["generator_kw"] == 0.0:
            self.events.append({"timestamp": timestamp, "event": TwinEvent.GENERATOR_STOPPED, "details": "Generator stopped."})
            
        if self.battery_state["soc"] >= 25.0 and telemetry["battery_soc"] < 25.0:
            self.events.append({"timestamp": timestamp, "event": TwinEvent.BATTERY_LOW, "details": "Battery SOC dropped below 25%."})
            
        if self.generator_state["fuel_liters"] >= 15.0 and telemetry["generator_fuel_liters"] < 15.0:
            self.events.append({"timestamp": timestamp, "event": TwinEvent.FUEL_LOW, "details": "Generator fuel dropped below 15L."})

        # State Update
        self.last_update_time = timestamp
        
        self.grid_state["is_available"] = telemetry["grid_available"]
        self.grid_state["voltage"] = telemetry["grid_voltage"]
        
        self.solar_state["generation_kw"] = telemetry["solar_kw"]
        
        self.battery_state["soc"] = telemetry["battery_soc"]
        self.battery_state["power_kw"] = telemetry["battery_kw"]
        
        self.generator_state["power_kw"] = telemetry["generator_kw"]
        self.generator_state["fuel_liters"] = telemetry["generator_fuel_liters"]
        
        self.load_state["critical_kw"] = telemetry["load_critical_kw"]
        self.load_state["important_kw"] = telemetry["load_important_kw"]
        self.load_state["flexible_kw"] = telemetry["load_flexible_kw"]
        self.load_state["unserved_kw"] = telemetry["unserved_kw"]

        self.history.append(self.get_current_state())
        if len(self.history) > 100:
            self.history.pop(0)

    def get_current_state(self) -> Dict[str, Any]:
        return {
            "last_update_time": self.last_update_time,
            "grid_state": self.grid_state.copy(),
            "solar_state": self.solar_state.copy(),
            "battery_state": self.battery_state.copy(),
            "generator_state": self.generator_state.copy(),
            "load_state": self.load_state.copy()
        }
