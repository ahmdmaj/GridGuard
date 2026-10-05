import enum
from typing import Dict, Any, List
import datetime
from dataclasses import dataclass, field

@dataclass
class DecisionConfig:
    v_support_enter: float = 0.94
    v_support_exit: float = 0.96
    v_island_enter: float = 0.85
    t_support_enter_s: float = 10.0
    t_normal_return_s: float = 600.0
    min_dwell_s: float = 30.0
    max_transfers_per_hour: int = 4
    generator_start_esh_hours: float = 2.0
    generator_stop_esh_hours: float = 12.0
    critical_reserve_soc: float = 30.0
    gen_start_delay_hours: float = 0.25
    gen_start_margin_hours: float = 0.5
    hard_start_soc: float = 20.0
    generator_stop_soc: float = 80.0
    shed_flexible_esh: float = 4.0
    reconnect_flexible_esh: float = 8.0
    shed_important_esh: float = 2.0
    reconnect_important_esh: float = 6.0
    reserve_floor_soc: float = 50.0
    pre_peak_start_h: float = 17.0
    pre_peak_end_h: float = 18.5
    pre_peak_soc_target: float = 90.0
    charge_power_cap_kw: float = 5.0

class EngineMode(enum.Enum):
    NORMAL = "NORMAL"
    SUPPORT = "SUPPORT"
    ISLAND = "ISLAND"
    GENERATOR_ASSIST = "GENERATOR_ASSIST"

class DecisionEngine:
    def __init__(self, config: dict | DecisionConfig = None) -> None:
        if isinstance(config, dict):
            self.cfg = DecisionConfig(**{k: v for k, v in config.items() if hasattr(DecisionConfig, k)})
        elif isinstance(config, DecisionConfig):
            self.cfg = config
        else:
            self.cfg = DecisionConfig()
            
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
        if not grid_connected or v_pcc < self.cfg.v_island_enter:
            self.time_v_below_enter += dt_s
            self.time_v_above_exit = 0.0
        elif v_pcc < self.cfg.v_support_enter:
            self.time_v_below_enter += dt_s
            self.time_v_above_exit = 0.0
        elif v_pcc >= self.cfg.v_support_exit:
            self.time_v_above_exit += dt_s
            self.time_v_below_enter = 0.0
        else:
            self.time_v_below_enter = 0.0
            self.time_v_above_exit = 0.0
            
        trace = []
            
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
        is_pre_peak = self.cfg.pre_peak_start_h <= current_hour < self.cfg.pre_peak_end_h
        charge_cap_kw = None
        
        if not grid_connected or v_pcc < self.cfg.v_island_enter:
            target_mode = EngineMode.ISLAND
        elif v_pcc < self.cfg.v_support_enter and self.time_v_below_enter >= self.cfg.t_support_enter_s:
            if target_mode == EngineMode.NORMAL:
                target_mode = EngineMode.SUPPORT
        elif v_pcc >= self.cfg.v_support_exit and self.time_v_above_exit >= self.cfg.t_normal_return_s:
            if target_mode in [EngineMode.SUPPORT, EngineMode.ISLAND]:
                target_mode = EngineMode.NORMAL
                
        # If we are supposed to be NORMAL but it's pre-peak and SOC is low, stay NORMAL but set charge limit
        if target_mode == EngineMode.NORMAL and is_pre_peak and soc < self.cfg.pre_peak_soc_target:
            charge_cap_kw = self.cfg.charge_power_cap_kw
            trace.append(f"Pre-peak charging active. Limiting charge power to {charge_cap_kw}kW.")
                
        # Protect against thrashing limits
        if target_mode != self.current_mode:
            protective_rank = {EngineMode.ISLAND: 3, EngineMode.SUPPORT: 2, EngineMode.NORMAL: 1, EngineMode.GENERATOR_ASSIST: 4}
            
            if protective_rank[target_mode] < protective_rank[self.current_mode]:
                if len(self.transfers_h) >= self.cfg.max_transfers_per_hour or self.time_in_mode_s < self.cfg.min_dwell_s:
                    trace.append("Thrashing protection active. Delaying return to lower protective state.")
                    target_mode = self.current_mode # Hold more protective mode
            
        if target_mode != self.current_mode:
            self.transfers_h.append(current_time_s)
            self.current_mode = target_mode
            self.time_in_mode_s = 0.0
            
        # Load shedding logic (F3: Critical Reserve SOC)
        if soc <= self.cfg.critical_reserve_soc:
            if self.connect_flexible or self.connect_important:
                trace.append(f"Emergency shed: SOC {soc:.1f}% <= {self.cfg.critical_reserve_soc}%")
            self.connect_flexible = False
            self.connect_important = False
        else:
            if self.connect_flexible:
                if full_esh.get("all_loads_hours", 100.0) < self.cfg.shed_flexible_esh:
                    trace.append(f"Shed flexible: full ESH {full_esh.get('all_loads_hours')}h < {self.cfg.shed_flexible_esh}h")
                    self.connect_flexible = False
            else:
                if full_esh.get("critical_and_important_hours", 0.0) >= self.cfg.reconnect_flexible_esh:
                    trace.append(f"Reconnect flexible: crit+imp ESH {full_esh.get('critical_and_important_hours')}h >= {self.cfg.reconnect_flexible_esh}h")
                    self.connect_flexible = True

            if self.connect_important:
                if full_esh.get("critical_and_important_hours", 100.0) < self.cfg.shed_important_esh:
                    trace.append(f"Shed important: crit+imp ESH {full_esh.get('critical_and_important_hours')}h < {self.cfg.shed_important_esh}h")
                    self.connect_important = False
            else:
                if full_esh.get("critical_only_hours", 0.0) >= self.cfg.reconnect_important_esh:
                    trace.append(f"Reconnect important: crit only ESH {full_esh.get('critical_only_hours')}h >= {self.cfg.reconnect_important_esh}h")
                    self.connect_important = True

        # Generator logic (F3: Start when shadow_esh critical worst case <= T_gen_delay + T_margin)
        if target_mode == EngineMode.NORMAL:
            if self.generator_requested:
                trace.append("Grid restored to NORMAL, stopping generator.")
            self.generator_requested = False
        else:
            if not self.generator_requested:
                if soc <= (self.cfg.hard_start_soc + 1.0):
                    trace.append(f"Generator hard start: SOC {soc:.1f}% <= {self.cfg.hard_start_soc + 1.0}%")
                    self.generator_requested = True
                elif shadow_esh.get("critical_only_hours", 100.0) < self.cfg.generator_start_esh_hours:
                    trace.append(f"Generator proactive start: Battery ESH {shadow_esh.get('critical_only_hours')}h < {self.cfg.generator_start_esh_hours}h")
                    self.generator_requested = True
                elif shadow_esh.get("critical_only_hours", 100.0) <= (self.cfg.gen_start_delay_hours + self.cfg.gen_start_margin_hours):
                    trace.append(f"Generator delayed start: Battery ESH {shadow_esh.get('critical_only_hours')}h <= delay+margin")
                    self.generator_requested = True
            else:
                if soc >= self.cfg.generator_stop_soc:
                    trace.append(f"Generator normal stop: SOC {soc:.1f}% >= {self.cfg.generator_stop_soc}%")
                    self.generator_requested = False
                
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
            "reason": f"Mode: {self.current_mode.value}. V_pcc: {v_pcc:.3f}",
            "trace": trace
        }
        
        if charge_cap_kw is not None:
            command["charge_limit_kw"] = charge_cap_kw
            
        return command
