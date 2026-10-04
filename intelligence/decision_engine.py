import enum
from typing import Dict, Any, List
import datetime

class EngineMode(enum.Enum):
    NORMAL = "NORMAL"
    SUPPORT = "SUPPORT"
    ISLAND = "ISLAND"
    GENERATOR_ASSIST = "GENERATOR_ASSIST"

class DecisionEngine:
    def __init__(self, config: dict = None) -> None:
        cfg = config or {}
        
        # Voltage thresholds
        self.v_support_enter = cfg.get("v_support_enter", 0.94)
        self.v_support_exit = cfg.get("v_support_exit", 0.96)
        self.v_island_enter = cfg.get("v_island_enter", 0.85)
        
        # Time thresholds
        self.t_support_enter_s = cfg.get("t_support_enter_s", 10.0)
        self.t_normal_return_s = cfg.get("t_normal_return_s", 600.0)
        self.min_dwell_s = cfg.get("min_dwell_s", 30.0)
        
        # Transfers
        self.max_transfers_per_hour = cfg.get("max_transfers_per_hour", 4)
        
        # Generator ESH
        self.generator_start_esh_hours = cfg.get("generator_start_esh_hours", 2.0)
        self.generator_stop_esh_hours = cfg.get("generator_stop_esh_hours", 12.0)
        self.critical_reserve_soc = cfg.get("critical_reserve_soc", 30.0)
        self.gen_start_delay_hours = cfg.get("gen_start_delay_hours", 0.25)
        self.gen_start_margin_hours = cfg.get("gen_start_margin_hours", 0.5)
        self.hard_start_soc = cfg.get("hard_start_soc", 20.0)
        self.hysteresis_stop_soc = cfg.get("generator_stop_soc", 80.0)
        
        # Shedding ESH
        self.shed_flexible_esh = cfg.get("shed_flexible_esh", 4.0)
        self.reconnect_flexible_esh = cfg.get("reconnect_flexible_esh", 8.0)
        self.shed_important_esh = cfg.get("shed_important_esh", 2.0)
        self.reconnect_important_esh = cfg.get("reconnect_important_esh", 6.0)
        
        # Reserve floor
        self.reserve_floor_soc = cfg.get("reserve_floor_soc", 50.0)
        
        # Time logic for pre-peak charging
        self.pre_peak_start_h = cfg.get("pre_peak_start_h", 17.0)
        self.pre_peak_end_h = cfg.get("pre_peak_end_h", 18.5)
        self.pre_peak_soc_target = cfg.get("pre_peak_soc_target", 90.0)
        self.charge_power_cap_kw = cfg.get("charge_power_cap_kw", 5.0) # Limit to avoid worsening feeder voltage

        # State
        self.current_mode = EngineMode.NORMAL
        self.time_in_mode_s = 0.0
        
        self.time_v_below_enter = 0.0
        self.time_v_above_exit = 0.0
        
        self.transfers_h: List[float] = [] # timestamps in seconds
        
        self.connect_flexible = True
        self.connect_important = True
        self.generator_requested = False

    def _prune_transfers(self, current_time_s: float) -> None:
        self.transfers_h = [t for t in self.transfers_h if current_time_s - t < 3600.0]

    def evaluate(self, dt_s: float, current_time_s: float, telemetry: Dict[str, Any], full_esh: Dict[str, float], shadow_esh: Dict[str, float] = None) -> Dict[str, Any]:
        if shadow_esh is None:
            shadow_esh = full_esh
            
        self.time_in_mode_s += dt_s
        self._prune_transfers(current_time_s)
        
        v_pcc = telemetry.get("v_rms_pu", 1.0)
        grid_connected = telemetry.get("grid_connected", True)
        soc = telemetry.get("soc", 100.0)
        
        # Track voltage timers
        if not grid_connected or v_pcc < self.v_island_enter:
            self.time_v_below_enter += dt_s
            self.time_v_above_exit = 0.0
        elif v_pcc < self.v_support_enter:
            self.time_v_below_enter += dt_s
            self.time_v_above_exit = 0.0
        elif v_pcc >= self.v_support_exit:
            self.time_v_above_exit += dt_s
            self.time_v_below_enter = 0.0
        else:
            self.time_v_below_enter = 0.0
            self.time_v_above_exit = 0.0
            
        # Determine base grid/inverter state
        target_mode = self.current_mode
        
        # Parse current hour from ISO format ts if available
        ts_str = telemetry.get("ts", "")
        current_hour = 12.0 # Default if missing
        if ts_str:
            try:
                # Remove Z and parse
                dt = datetime.datetime.fromisoformat(ts_str.replace("Z", "+00:00"))
                current_hour = dt.hour + dt.minute / 60.0
            except Exception:
                pass
        
        # Pre-peak charging logic
        is_pre_peak = self.pre_peak_start_h <= current_hour < self.pre_peak_end_h
        charge_cap_kw = None
        
        if not grid_connected or v_pcc < self.v_island_enter:
            target_mode = EngineMode.ISLAND
        elif v_pcc < self.v_support_enter and self.time_v_below_enter >= self.t_support_enter_s:
            if target_mode == EngineMode.NORMAL:
                target_mode = EngineMode.SUPPORT
        elif v_pcc >= self.v_support_exit and self.time_v_above_exit >= self.t_normal_return_s and soc >= self.reserve_floor_soc:
            if target_mode in [EngineMode.SUPPORT, EngineMode.ISLAND]:
                target_mode = EngineMode.NORMAL
                
        # If we are supposed to be NORMAL but it's pre-peak and SOC is low, override to SUPPORT
        if target_mode == EngineMode.NORMAL and is_pre_peak and soc < self.pre_peak_soc_target:
            target_mode = EngineMode.SUPPORT
            charge_cap_kw = self.charge_power_cap_kw
                
        # Protect against thrashing limits
        if target_mode != self.current_mode:
            # If we are trying to go to a LESS protective mode, check limits
            # ISLAND > SUPPORT > NORMAL
            protective_rank = {EngineMode.ISLAND: 3, EngineMode.SUPPORT: 2, EngineMode.NORMAL: 1, EngineMode.GENERATOR_ASSIST: 4}
            
            if protective_rank[target_mode] < protective_rank[self.current_mode]:
                if len(self.transfers_h) >= self.max_transfers_per_hour or self.time_in_mode_s < self.min_dwell_s:
                    target_mode = self.current_mode # Hold more protective mode
            
        if target_mode != self.current_mode:
            self.transfers_h.append(current_time_s)
            self.current_mode = target_mode
            self.time_in_mode_s = 0.0
            
        # Load shedding logic (F3: Critical Reserve SOC)
        # If SOC falls below critical_reserve_soc, shed everything except critical load
        if soc <= self.critical_reserve_soc:
            self.connect_flexible = False
            self.connect_important = False
        else:
            if full_esh.get("all_loads_hours", 100.0) < self.shed_flexible_esh:
                self.connect_flexible = False
            elif full_esh.get("critical_and_important_hours", 0.0) >= self.reconnect_flexible_esh:
                self.connect_flexible = True

            if full_esh.get("critical_and_important_hours", 100.0) < self.shed_important_esh:
                self.connect_important = False
            elif full_esh.get("critical_only_hours", 0.0) >= self.reconnect_important_esh:
                self.connect_important = True

        # Generator logic (F3: Start when ESH_island_critical_worst_case <= T_gen_delay + T_margin)
        if not self.generator_requested:
            # We add a 1% buffer to hard_start_soc to ensure we don't fall below exactly 20.0% due to discrete steps
            if soc <= (self.hard_start_soc + 1.0):
                self.generator_requested = True
            elif shadow_esh.get("critical_only_hours", 100.0) <= (self.gen_start_delay_hours + self.gen_start_margin_hours):
                self.generator_requested = True
        else:
            if soc >= self.hysteresis_stop_soc:
                self.generator_requested = False
            # Remove the short-cycling ESH stop logic that was incorrectly including fuel
                
        if self.generator_requested:
            self.current_mode = EngineMode.GENERATOR_ASSIST
        elif self.current_mode == EngineMode.GENERATOR_ASSIST:
            # If generator was requested but is now false, and grid is still dead, go back to ISLAND
            self.current_mode = EngineMode.ISLAND
        if self.current_mode == EngineMode.NORMAL:
            inv_mode = "GRID_PASS"
        elif self.current_mode == EngineMode.SUPPORT:
            inv_mode = "SUPPORT"
        else: # ISLAND or GENERATOR_ASSIST
            inv_mode = "ISLAND"
            
        shed_tier = 0
        if not self.connect_important:
            shed_tier = 2
        elif not self.connect_flexible:
            shed_tier = 1
            
        gen_cmd = "START" if self.generator_requested else "STOP"
        
        command = {
            "inverter_mode": inv_mode,
            "shed_tier": shed_tier,
            "gen_cmd": gen_cmd,
            "reason": f"Mode: {self.current_mode.value}. V_pcc: {v_pcc:.3f}"
        }
        
        if charge_cap_kw is not None:
            command["charge_limit_kw"] = charge_cap_kw
            
        return command
