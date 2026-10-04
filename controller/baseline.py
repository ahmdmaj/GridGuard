from typing import Dict, Any
from simulator.constants import OperatingMode
from controller.command import SystemCommand

class BaselineController:
    def __init__(self) -> None:
        self.current_mode: OperatingMode = OperatingMode.NORMAL
        
        # Add new state and config (Phase G)
        self.generator_capacity_kw = 15.0
        self.connect_flexible = True
        self.connect_important = True

    def evaluate(self, twin_state: Dict[str, Any]) -> SystemCommand:
        is_grid_available = twin_state["grid_state"]["is_available"]
        soc = twin_state["battery_state"]["soc"]

        if is_grid_available:
            self.current_mode = OperatingMode.NORMAL
            self.connect_flexible = True
            self.connect_important = True
            
            if soc < 100.0:
                battery_command_kw = -20.0
                reason = "Baseline: Grid is normal. Charging battery."
            else:
                battery_command_kw = 0.0
                reason = "Baseline: Grid is normal. All loads connected."

            return {
                "battery_command_kw": battery_command_kw,
                "generator_run": False,
                "connect_critical": True,
                "connect_important": True,
                "connect_flexible": True,
                "decision_reason": reason
            }
        else:
            self.current_mode = OperatingMode.GRID_FAILED
            generator_run = True

            # Dumb SOC-based Load Shedding Hysteresis (Phase G)
            if self.connect_flexible:
                if soc < 50.0:
                    self.connect_flexible = False
            else:
                if soc >= 70.0:
                    self.connect_flexible = True

            if self.connect_important:
                if soc < 20.0:
                    self.connect_important = False
            else:
                if soc >= 40.0:
                    self.connect_important = True

            if not self.connect_important:
                reason = "Baseline: Grid failed, SOC low, shedding important and flexible."
            elif not self.connect_flexible:
                reason = "Baseline: Grid failed, activating generator and shedding flexible."
            else:
                reason = "Baseline: Grid failed, activating generator. All loads connected."

            active_load_kw = twin_state["load_state"]["critical_kw"]
            if self.connect_important:
                active_load_kw += twin_state["load_state"]["important_kw"]
            if self.connect_flexible:
                active_load_kw += twin_state["load_state"]["flexible_kw"]

            solar_kw = twin_state["solar_state"]["generation_kw"]
            
            # Phase G Fix: Deduct generator capacity from battery command
            battery_command_kw = active_load_kw - solar_kw - self.generator_capacity_kw

            return {
                "battery_command_kw": battery_command_kw,
                "generator_run": generator_run,
                "connect_critical": True,
                "connect_important": self.connect_important,
                "connect_flexible": self.connect_flexible,
                "decision_reason": reason
            }
