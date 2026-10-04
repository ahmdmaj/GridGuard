from typing import Dict, Any

class BaselineHysteresisController:
    """
    Representative of a basic UPS + generator setup.
    - Switches to battery (ISLAND) on V < 0.94, instantly, no hysteresis or dwell time.
    - Generator starts strictly when SOC < 30%.
    - No pre-peak charging.
    """
    def __init__(self) -> None:
        self.generator_start_soc = 30.0
        self.generator_stop_soc = 90.0
        
        self.shed_flexible_soc = 50.0
        self.reconnect_flexible_soc = 70.0
        
        self.shed_important_soc = 20.0
        self.reconnect_important_soc = 40.0
        
        self.generator_requested = False
        self.connect_flexible = True
        self.connect_important = True

    def evaluate(self, dt_s: float, current_time_s: float, telemetry: Dict[str, Any]) -> Dict[str, Any]:
        v_pcc = telemetry.get("v_rms_pu", 1.0)
        grid_connected = telemetry.get("grid_connected", True)
        soc = telemetry.get("soc", 100.0)
        
        # Grid/Inverter state
        # Very simple rules: if voltage is bad, Island. If good, Grid Pass.
        if not grid_connected or v_pcc < 0.94:
            inv_mode = "ISLAND"
        else:
            inv_mode = "GRID_PASS"
            
        # Generator state
        if not self.generator_requested and soc < self.generator_start_soc:
            self.generator_requested = True
        elif self.generator_requested and soc >= self.generator_stop_soc:
            self.generator_requested = False
            
        gen_cmd = "START" if self.generator_requested else "STOP"
        
        # Shedding
        if self.connect_flexible:
            if soc < self.shed_flexible_soc:
                self.connect_flexible = False
        else:
            if soc >= self.reconnect_flexible_soc:
                self.connect_flexible = True

        if self.connect_important:
            if soc < self.shed_important_soc:
                self.connect_important = False
        else:
            if soc >= self.reconnect_important_soc:
                self.connect_important = True
                
        shed_tier = 0
        if not self.connect_important:
            shed_tier = 2
        elif not self.connect_flexible:
            shed_tier = 1
            
        return {
            "inverter_mode": inv_mode,
            "shed_tier": shed_tier,
            "gen_cmd": gen_cmd,
            "reason": f"Baseline UPS logic. V: {v_pcc:.3f}, SOC: {soc:.1f}%"
        }
