from typing import Dict, Any
from simulator.constants import OperatingMode
from controller.command import SystemCommand

class DecisionEngine:
    def __init__(self, config: dict = None) -> None:
        cfg = config or {}
        self.generator_capacity_kw = cfg.get("generator_capacity_kw", 15.0)
        self.hysteresis_start_soc = cfg.get("generator_start_soc", 30.0)
        self.hysteresis_stop_soc = cfg.get("generator_stop_soc", 80.0)
        
        self.current_mode: OperatingMode = OperatingMode.NORMAL
        self.generator_requested: bool = False

    def evaluate(self, twin_state: Dict[str, Any], instantaneous_esh: Dict[str, float]) -> SystemCommand:
        is_grid_available = twin_state["grid_state"]["is_available"]

        if is_grid_available:
            self.current_mode = OperatingMode.NORMAL
            self.generator_requested = False
            return {
                "battery_command_kw": 0.0,
                "generator_run": False,
                "connect_critical": True,
                "connect_important": True,
                "connect_flexible": True,
                "decision_reason": "Grid is available. Normal operation."
            }
        else:
            # Step 2: Grid Failed - Generator Hysteresis
            soc = twin_state["battery_state"]["soc"]
            if soc <= self.hysteresis_start_soc and not self.generator_requested:
                self.generator_requested = True
            elif soc >= self.hysteresis_stop_soc and self.generator_requested:
                self.generator_requested = False

            # Step 3: Grid Failed - Load Shedding via ESH
            connect_critical = True
            if instantaneous_esh["all_loads_hours"] >= 4.0:
                self.current_mode = OperatingMode.GRID_FAILED
                connect_important = True
                connect_flexible = True
                reason = "Grid failed. ESH healthy (>4h). All loads retained."
            elif instantaneous_esh["critical_and_important_hours"] >= 2.0:
                self.current_mode = OperatingMode.GRID_FAILED
                connect_important = True
                connect_flexible = False
                reason = "Grid failed. ESH declining. Shedding flexible loads."
            else:
                self.current_mode = OperatingMode.ENERGY_SCARCITY
                connect_important = False
                connect_flexible = False
                reason = "Grid failed. Critical ESH scarcity. Protecting critical loads only."

            # Step 4: Grid Failed - Source Management
            active_load_kw = 0.0
            if connect_critical:
                active_load_kw += twin_state["load_state"]["critical_kw"]
            if connect_important:
                active_load_kw += twin_state["load_state"]["important_kw"]
            if connect_flexible:
                active_load_kw += twin_state["load_state"]["flexible_kw"]

            deficit_kw = active_load_kw - twin_state["solar_state"]["generation_kw"]
            
            if self.generator_requested:
                # Generator is ON: Generator covers the load, remaining capacity charges the battery
                battery_command_kw = deficit_kw - self.generator_capacity_kw
            else:
                # Generator is OFF: Battery covers the net deficit (or charges from surplus solar)
                battery_command_kw = deficit_kw

            # Step 5: Return command
            return {
                "battery_command_kw": battery_command_kw,
                "generator_run": self.generator_requested,
                "connect_critical": connect_critical,
                "connect_important": connect_important,
                "connect_flexible": connect_flexible,
                "decision_reason": reason
            }
