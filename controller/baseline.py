from typing import Dict, Any
from simulator.constants import OperatingMode
from controller.command import SystemCommand

class BaselineController:
    def __init__(self) -> None:
        self.current_mode: OperatingMode = OperatingMode.NORMAL

    def evaluate(self, twin_state: Dict[str, Any]) -> SystemCommand:
        is_grid_available = twin_state["grid_state"]["is_available"]

        if is_grid_available:
            self.current_mode = OperatingMode.NORMAL
            return {
                "battery_command_kw": 0.0,
                "generator_run": False,
                "connect_critical": True,
                "connect_important": True,
                "connect_flexible": True,
                "decision_reason": "Baseline: Grid is normal. All loads connected."
            }
        else:
            self.current_mode = OperatingMode.GRID_FAILED
            soc = twin_state["battery_state"]["soc"]
            generator_run = True

            if soc > 20.0:
                connect_critical = True
                connect_important = True
                connect_flexible = False
                reason = "Baseline: Grid failed, activating generator and shedding flexible."
            else:
                connect_critical = True
                connect_important = False
                connect_flexible = False
                reason = "Baseline: Grid failed, SOC low, shedding important and flexible."

            active_load_kw = 0.0
            if connect_critical:
                active_load_kw += twin_state["load_state"]["critical_kw"]
            if connect_important:
                active_load_kw += twin_state["load_state"]["important_kw"]
            if connect_flexible:
                active_load_kw += twin_state["load_state"]["flexible_kw"]

            solar_kw = twin_state["solar_state"]["generation_kw"]
            battery_command_kw = active_load_kw - solar_kw

            return {
                "battery_command_kw": battery_command_kw,
                "generator_run": generator_run,
                "connect_critical": connect_critical,
                "connect_important": connect_important,
                "connect_flexible": connect_flexible,
                "decision_reason": reason
            }
