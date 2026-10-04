from simulator.constants import SIMULATION_TIMESTEP_MINUTES

class Generator:
    def __init__(self) -> None:
        self.capacity_kw: float = 15.0
        self.fuel_liters: float = 100.0
        self.max_fuel_liters: float = 100.0
        self.fuel_consumption_liters_per_kwh: float = 0.3
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
        energy_kwh = actual_power_kw * (duration_minutes / 60.0)
        fuel_needed = energy_kwh * self.fuel_consumption_liters_per_kwh

        if fuel_needed > self.fuel_liters:
            energy_kwh = self.fuel_liters / self.fuel_consumption_liters_per_kwh
            actual_power_kw = energy_kwh / (duration_minutes / 60.0)
            self.fuel_liters = 0.0
            self.stop()
        else:
            self.fuel_liters -= fuel_needed

        return actual_power_kw
