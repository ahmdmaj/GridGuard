import enum
from typing import Dict, Any, Tuple

class InverterMode(enum.Enum):
    GRID_PASS = "GRID_PASS"
    SUPPORT = "SUPPORT"
    ISLAND = "ISLAND"

class InverterSTS:
    def __init__(self, config: Dict[str, Any]) -> None:
        self.inverter_rating_kw = config.get("inverter_rating_kw", 20.0)
        self.battery_max_discharge_kw = config.get("battery_max_discharge_kw", 20.0)
        self.efficiency = config.get("efficiency", 0.95)
        self.transfer_time_ms = config.get("transfer_time_ms", 10.0)
        self.min_dwell_s = config.get("min_dwell_s", 5.0)
        
        self.current_mode = InverterMode.GRID_PASS
        self.time_in_mode_s = self.min_dwell_s

    def step(self, target_mode: InverterMode, dt_s: float, pcc_v_pu: float, load_kw: float) -> Tuple[float, float, bool]:
        """
        Steps the inverter model.
        Returns:
            critical_bus_v_pu: The voltage on the critical bus.
            dropout_ms: Dropout time experienced during this step (due to transfer).
            overload: True if the inverter rating was exceeded.
        """
        dropout_ms = 0.0
        
        # Enforce min dwell time
        if target_mode != self.current_mode:
            if self.time_in_mode_s >= self.min_dwell_s:
                self.current_mode = target_mode
                self.time_in_mode_s = 0.0
                dropout_ms = self.transfer_time_ms
        
        self.time_in_mode_s += dt_s
        
        overload = False
        critical_bus_v_pu = 1.0

        if self.current_mode == InverterMode.GRID_PASS:
            # Critical bus matches PCC voltage
            critical_bus_v_pu = pcc_v_pu
            # In pass-through, the inverter rating does not limit the load (it's bypassing)
            # Actually, static transfer switch might have a rating, but assume infinite or very high for pass-through
        else:
            # SUPPORT or ISLAND mode: inverter creates the waveform
            if load_kw > self.inverter_rating_kw:
                overload = True
                # Voltage collapses proportionally to the overload (simple model)
                critical_bus_v_pu = self.inverter_rating_kw / load_kw
            else:
                critical_bus_v_pu = 1.0
                
        return critical_bus_v_pu, dropout_ms, overload
