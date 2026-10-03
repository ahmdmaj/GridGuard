from simulator.constants import SIMULATION_TIMESTEP_MINUTES

class Battery:
    def __init__(self) -> None:
        self.capacity_kwh: float = 40.0
        self.current_energy_kwh: float = 40.0
        self.max_charge_power_kw: float = 20.0
        self.max_discharge_power_kw: float = 20.0
        self.min_soc_percent: float = 20.0
        self.max_soc_percent: float = 100.0
        self.charge_efficiency: float = 0.95
        self.discharge_efficiency: float = 0.95

    @property
    def soc(self) -> float:
        """Returns the current State of Charge as a percentage (0.0 to 100.0)."""
        return (self.current_energy_kwh / self.capacity_kwh) * 100.0

    def charge(self, power_kw: float, duration_minutes: float = SIMULATION_TIMESTEP_MINUTES) -> float:
        actual_power_kw = min(power_kw, self.max_charge_power_kw)
        room_kwh = (self.capacity_kwh * (self.max_soc_percent / 100.0)) - self.current_energy_kwh
        energy_to_store = actual_power_kw * (duration_minutes / 60.0) * self.charge_efficiency

        stored_energy = min(energy_to_store, max(0.0, room_kwh))
        
        self.current_energy_kwh += stored_energy
        
        return stored_energy / self.charge_efficiency / (duration_minutes / 60.0)

    def discharge(self, power_kw: float, duration_minutes: float = SIMULATION_TIMESTEP_MINUTES) -> float:
        actual_power_kw = min(power_kw, self.max_discharge_power_kw)
        available_kwh = self.current_energy_kwh - (self.capacity_kwh * (self.min_soc_percent / 100.0))
        energy_to_drain = (actual_power_kw * (duration_minutes / 60.0)) / self.discharge_efficiency

        drained_energy = min(energy_to_drain, max(0.0, available_kwh))
        
        self.current_energy_kwh -= drained_energy
        
        return drained_energy * self.discharge_efficiency / (duration_minutes / 60.0)
