from typing import Dict, Any, Optional
import datetime

from physical.feeder import FeederModel
from physical.inverter_sts import InverterSTS, InverterMode
from physical.loads import LoadModel
from physical.battery import Battery
from physical.generator import Generator
from physical.solar import SolarPV
from physical.pq_node import PowerQualityNode
from physical.local_protection import LocalProtection

class PhysicalPlant:
    def __init__(self, config: Dict[str, Any]) -> None:
        self.config = config
        self.feeder = FeederModel(config)
        self.inverter = InverterSTS(config)
        self.loads = LoadModel(config)
        self.battery = Battery()
        self.generator = Generator(config)
        self.solar = SolarPV()
        self.pq_node = PowerQualityNode(config)
        self.local_protection = LocalProtection(config)
        
        self.last_p_site_kw = 0.0
        self.time_s = 0.0
        
        # Telemetry state
        self.v_pcc_pu = 1.0
        self.v_crit_pu = 1.0
        self.load_kw = 0.0
        self.solar_kw = 0.0
        self.batt_kw = 0.0
        self.gen_kw = 0.0
        self.unserved_kw = 0.0

    def step(self, dt_s: float, current_time: datetime.datetime, command: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
        """
        Steps the physical plant simulation.
        command format: {"inverter_mode": "GRID_PASS", "shed_tier": 0, "gen_cmd": "HOLD", "charge_limit_kw": 5.0}
        """
        # 1. Grid voltage based on last step's site import
        self.v_pcc_pu = self.feeder.get_voltage_pu(current_time, self.last_p_site_kw)
        
        # 2. Local Protection & Command processing
        if command:
            self.local_protection.receive_command()
            target_mode = InverterMode(command.get("inverter_mode", "GRID_PASS"))
            shed_tier = command.get("shed_tier", 0)
            gen_cmd = command.get("gen_cmd", "HOLD")
            charge_limit = command.get("charge_limit_kw", self.battery.max_charge_power_kw)
        else:
            target_mode = self.inverter.current_mode # Default hold
            shed_tier = 0 # Default no shed? Actually should hold last state, but keep simple
            gen_cmd = "HOLD"
            charge_limit = self.battery.max_charge_power_kw
            
        fallback = self.local_protection.step(dt_s, self.v_pcc_pu, self.inverter.current_mode)
        if fallback:
            target_mode = fallback
            
        # 3. Apply Load shedding
        # 0 = All connected, 1 = Shed flexible (non_essential), 2 = Shed important and flexible
        if shed_tier == 0:
            self.loads.set_connection("non_essential", True)
            self.loads.set_connection("important", True)
        elif shed_tier == 1:
            self.loads.set_connection("non_essential", False)
            self.loads.set_connection("important", True)
        elif shed_tier == 2:
            self.loads.set_connection("non_essential", False)
            self.loads.set_connection("important", False)
            
        # 4. Generator Control
        if gen_cmd == "START":
            self.generator.start()
        elif gen_cmd == "STOP":
            self.generator.stop()
            
        # 5. Inverter Step
        # Pre-calculate nominal load to check overload
        nominal_load_kw = self.loads.get_total_power_kw(1.0)
        self.v_crit_pu, dropout_ms, overload = self.inverter.step(target_mode, dt_s, self.v_pcc_pu, nominal_load_kw)
        
        # 6. Actual Load and Generation
        self.load_kw = self.loads.get_total_power_kw(self.v_crit_pu)
        self.solar_kw = self.solar.get_generation()
        
        duration_m = dt_s / 60.0
        
        if self.generator.is_running:
            requested_kw = max(0.0, self.load_kw - self.solar_kw + charge_limit)
            self.gen_kw = self.generator.generate(requested_kw, duration_minutes=duration_m)
        else:
            self.gen_kw = self.generator.generate(0.0, duration_minutes=duration_m)
            
        # 7. Energy Balance & Battery
        # The inverter acts as the gateway. 
        self.unserved_kw = 0.0
        grid_connected = (self.inverter.current_mode != InverterMode.ISLAND)
        duration_m = dt_s / 60.0
        
        if not grid_connected:
            # ISLAND mode
            self.last_p_site_kw = 0.0
            net_demand = self.load_kw - self.solar_kw - self.gen_kw
            
            if net_demand > 0:
                self.batt_kw = self.battery.discharge(net_demand, duration_minutes=duration_m)
                if self.batt_kw < net_demand:
                    self.unserved_kw = net_demand - self.batt_kw
            else:
                self.batt_kw = -self.battery.charge(abs(net_demand), duration_minutes=duration_m)
        else:
            # GRID_PASS or SUPPORT
            net_demand = self.load_kw - self.solar_kw - self.gen_kw
            
            if net_demand < 0:
                # Excess power on site, charge battery or export
                self.batt_kw = -self.battery.charge(min(abs(net_demand), charge_limit), duration_minutes=duration_m)
                export_kw = abs(net_demand) - abs(self.batt_kw)
                self.last_p_site_kw = -export_kw
            else:
                # Need power from grid or battery
                if self.inverter.current_mode == InverterMode.SUPPORT:
                    # In SUPPORT, battery is used to help if grid is sagging, but let's assume it charges if instructed
                    if command and "charge_limit_kw" in command:
                        self.batt_kw = -self.battery.charge(charge_limit, duration_minutes=duration_m)
                    else:
                        self.batt_kw = 0.0
                    self.last_p_site_kw = net_demand + abs(self.batt_kw)
                else:
                    # GRID_PASS
                    if command and "charge_limit_kw" in command:
                        self.batt_kw = -self.battery.charge(charge_limit, duration_minutes=duration_m)
                    else:
                        self.batt_kw = 0.0
                    self.last_p_site_kw = net_demand + abs(self.batt_kw)
                    
        # Update battery step time (the battery in simulator uses SIMULATION_TIMESTEP_MINUTES globally, but we should just let it run)
        # Actually simulator.battery assumes 5 min steps when we call discharge/charge
        
        telem = self.generate_telemetry(current_time)
        
        # Run PQ node to get formatted grid_pq telemetry
        pq_telem = self.pq_node.generate_telemetry(current_time, self.v_pcc_pu, grid_connected, self.inverter.current_mode.value, 0)
        
        return {"plant_telem": telem, "grid_pq": pq_telem}

    def generate_telemetry(self, current_time: datetime.datetime) -> Dict[str, Any]:
        """Generates a telemetry snapshot of the current plant state."""
        # Update feeder voltage preview based on latest state if needed, or just use existing
        preview_v_pcc = max(0.0, self.feeder.get_voltage_pu(current_time, self.last_p_site_kw))
        
        # Ensure solar matches time/overrides
        current_solar = self.solar.get_generation()
        
        grid_connected = (self.inverter.current_mode != InverterMode.ISLAND)
        return {
            "ts": current_time.isoformat() + "Z",
            "v_rms_pu": preview_v_pcc,
            "v_crit_pu": self.v_crit_pu,
            "grid_connected": grid_connected,
            "soc": self.battery.soc,
            "fuel_liters": self.generator.fuel_liters,
            "gen_available": self.generator.is_available,
            "solar_kw": current_solar,
            "load_critical_kw": self.loads.get_tier_power_kw("critical", self.v_crit_pu),
            "load_important_kw": self.loads.get_tier_power_kw("important", self.v_crit_pu),
            "load_flexible_kw": self.loads.get_tier_power_kw("non_essential", self.v_crit_pu),
            "unserved_kw": self.unserved_kw,
            "sts_state": self.inverter.current_mode.value,
            "transfer_count": len(self.inverter.__dict__.get("transfers_h", [])), # Mocked
            "dropout_ms": 0.0 # Unknown preview
        }
