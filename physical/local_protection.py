from typing import Dict, Any, Optional
from physical.inverter_sts import InverterMode

class LocalProtection:
    def __init__(self, config: Dict[str, Any]) -> None:
        self.watchdog_s = config.get("watchdog_s", 30.0)
        self.time_since_last_cmd_s = 0.0
        
        # State tracking for rules
        self.time_v_below_092_s = 0.0
        self.time_v_above_096_s = 0.0
        
        self.active_fallback_mode: Optional[InverterMode] = None

    def receive_command(self) -> None:
        """Called when a valid command or heartbeat arrives."""
        self.time_since_last_cmd_s = 0.0
        self.active_fallback_mode = None
        self.time_v_below_092_s = 0.0
        self.time_v_above_096_s = 0.0

    def step(self, dt_s: float, v_pcc_pu: float, current_mode: InverterMode) -> Optional[InverterMode]:
        """
        Steps the protection logic.
        Returns the target InverterMode if fallback is active, otherwise None.
        """
        self.time_since_last_cmd_s += dt_s
        
        if self.time_since_last_cmd_s <= self.watchdog_s:
            return None # Comms are healthy, no fallback
            
        # Comms lost, apply local rules
        if self.active_fallback_mode is None:
            # Initialize fallback mode to current mode
            self.active_fallback_mode = current_mode
            
        # Track voltage conditions
        if v_pcc_pu < 0.80:
            self.active_fallback_mode = InverterMode.ISLAND
        elif v_pcc_pu < 0.92:
            self.time_v_below_092_s += dt_s
            self.time_v_above_096_s = 0.0
            if self.time_v_below_092_s >= 5.0 and self.active_fallback_mode != InverterMode.ISLAND:
                self.active_fallback_mode = InverterMode.SUPPORT
        elif v_pcc_pu >= 0.96:
            self.time_v_above_096_s += dt_s
            self.time_v_below_092_s = 0.0
            if self.time_v_above_096_s >= 600.0: # 10 minutes
                self.active_fallback_mode = InverterMode.GRID_PASS
        else:
            # Between 0.92 and 0.96, hold current mode, reset timers
            self.time_v_below_092_s = 0.0
            self.time_v_above_096_s = 0.0
            
        return self.active_fallback_mode
