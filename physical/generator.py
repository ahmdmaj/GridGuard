from simulator.constants import SIMULATION_TIMESTEP_MINUTES

from typing import Dict, Any
from simulator.constants import SIMULATION_TIMESTEP_MINUTES

class Generator:
    def __init__(self, config: Dict[str, Any] = None) -> None:
        cfg = config or {}
        self.capacity_kw: float = cfg.get("generator_capacity_kw", 15.0)
        self.fuel_liters: float = cfg.get("generator_tank_liters", 100.0)
        self.max_fuel_liters: float = cfg.get("generator_tank_liters", 100.0)
        
        # Reference estimate [cited from typical 15kW genset datasheets]:
        # Linear model: Fuel (L/h) = no_load_coeff * Rated_kW + load_coeff * Output_kW
        self.no_load_coeff: float = cfg.get("generator_no_load_coeff", 0.08)
        self.load_coeff: float = cfg.get("generator_load_coeff", 0.25)
        
        self.is_available: bool = True
        self.is_running: bool = False

    def start(self) -> None:
        if self.is_available and self.fuel_liters > 0:
            self.is_running = True

    def stop(self) -> None:
        self.is_running = False

    def set_availability(self, available: bool) -> None:
        self.is_available = available
        if not self.is_available:
            self.stop()

    def add_fuel(self, liters: float) -> None:
        self.fuel_liters = min(self.max_fuel_liters, self.fuel_liters + liters)

    def generate(self, requested_power_kw: float, duration_minutes: float = SIMULATION_TIMESTEP_MINUTES) -> float:
        if not self.is_running:
            return 0.0

        actual_power_kw = min(requested_power_kw, self.capacity_kw)
        hours = duration_minutes / 60.0
        
        fuel_rate_l_h = (self.no_load_coeff * self.capacity_kw) + (self.load_coeff * actual_power_kw)
        fuel_needed = fuel_rate_l_h * hours

        if fuel_needed > self.fuel_liters:
            # If fuel runs out during this step, prorate the generated energy
            fraction_run = self.fuel_liters / fuel_needed
            actual_power_kw = actual_power_kw * fraction_run
            self.fuel_liters = 0.0
            self.stop()
        else:
            self.fuel_liters -= fuel_needed

        return actual_power_kw
