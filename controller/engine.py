from typing import Dict, Any
from simulator.constants import OperatingMode
from controller.command import SystemCommand

class DecisionEngine:
    def __init__(self, config: dict = None) -> None:
        cfg = config or {}
        # Phase C
        self.generator_capacity_kw = cfg.get("generator_capacity_kw", 15.0)
        
        # Phase D
        self.generator_start_esh_hours = cfg.get("generator_start_esh_hours", 2.0)
        self.generator_stop_esh_hours = cfg.get("generator_stop_esh_hours", 12.0)
        self.hard_start_soc = cfg.get("hard_start_soc", 20.0)
        self.hysteresis_stop_soc = cfg.get("generator_stop_soc", 80.0)
        
        # Phase E
        self.shed_flexible_esh = cfg.get("shed_flexible_esh", 4.0)
        self.reconnect_flexible_esh = cfg.get("reconnect_flexible_esh", 8.0)
        self.shed_important_esh = cfg.get("shed_important_esh", 2.0)
        self.reconnect_important_esh = cfg.get("reconnect_important_esh", 6.0)
        
        # Phase F
        self.target_soc = cfg.get("target_soc", 100.0)
        self.max_charge_command_kw = cfg.get("max_charge_command_kw", 20.0)
        
        self.current_mode: OperatingMode = OperatingMode.NORMAL
        self.generator_requested: bool = False
        
        # Breaker state memory
        self.connect_flexible: bool = True
        self.connect_important: bool = True
        self.connect_critical: bool = True

    def evaluate(self, twin_state: 'DigitalTwinState', full_esh: Dict[str, float], battery_only_esh: Dict[str, float] = None) -> SystemCommand:
        if battery_only_esh is None:
            battery_only_esh = full_esh

        is_grid_available = twin_state.grid.is_available

        if is_grid_available:
            self.current_mode = OperatingMode.NORMAL
            self.generator_requested = False
            self.connect_flexible = True
            self.connect_important = True
            self.connect_critical = True
            
            soc = twin_state.battery.soc
            if soc < self.target_soc:
                battery_command_kw = -self.max_charge_command_kw
                reason = f"Grid is available. Charging battery to target SOC ({self.target_soc}%)."
            else:
                battery_command_kw = 0.0
                reason = "Grid is available. Battery at target SOC. Normal operation."

            return {
                "battery_command_kw": battery_command_kw,
                "generator_run": False,
                "connect_critical": True,
                "connect_important": True,
                "connect_flexible": True,
                "decision_reason": reason
            }
        else:
            # Step 2: Grid Failed - Generator Smart Dispatch (Phase D)
            soc = twin_state.battery.soc
            
            # Start logic
            if not self.generator_requested:
                if soc <= self.hard_start_soc:
                    self.generator_requested = True
                elif battery_only_esh.get("critical_only_hours", 0) < self.generator_start_esh_hours:
                    self.generator_requested = True
            
            # Stop logic
            if self.generator_requested:
                if soc >= self.hysteresis_stop_soc:
                    self.generator_requested = False
                elif battery_only_esh.get("all_loads_hours", 0) > self.generator_stop_esh_hours and soc > self.hard_start_soc:
                    self.generator_requested = False

            # Step 3: Grid Failed - Load Shedding via ESH (Phase E)
            # Flexible Load Logic
            if self.connect_flexible:
                if full_esh.get("all_loads_hours", 0) < self.shed_flexible_esh:
                    self.connect_flexible = False
            else:
                if full_esh.get("critical_and_important_hours", 0) >= self.reconnect_flexible_esh:
                    self.connect_flexible = True

            # Important Load Logic
            if self.connect_important:
                if full_esh.get("critical_and_important_hours", 0) < self.shed_important_esh:
                    self.connect_important = False
            else:
                if full_esh.get("critical_only_hours", 0) >= self.reconnect_important_esh:
                    self.connect_important = True

            # Determine mode based on breaker states
            if not self.connect_important:
                self.current_mode = OperatingMode.ENERGY_SCARCITY
                reason = "Grid failed. Critical ESH scarcity. Protecting critical loads only."
            elif not self.connect_flexible:
                self.current_mode = OperatingMode.GRID_FAILED
                reason = "Grid failed. ESH declining. Shedding flexible loads."
            else:
                self.current_mode = OperatingMode.GRID_FAILED
                reason = "Grid failed. ESH healthy. All loads retained."

            # Step 4: Grid Failed - Source Management
            active_load_kw = 0.0
            if self.connect_critical:
                active_load_kw += twin_state.loads.critical_kw
            if self.connect_important:
                active_load_kw += twin_state.loads.important_kw
            if self.connect_flexible:
                active_load_kw += twin_state.loads.flexible_kw

            deficit_kw = active_load_kw - twin_state.solar.power_kw
            
            if self.generator_requested:
                battery_command_kw = deficit_kw - self.generator_capacity_kw
            else:
                battery_command_kw = deficit_kw

            # Step 5: Return command
            return {
                "battery_command_kw": battery_command_kw,
                "generator_run": self.generator_requested,
                "connect_critical": self.connect_critical,
                "connect_important": self.connect_important,
                "connect_flexible": self.connect_flexible,
                "decision_reason": reason
            }
