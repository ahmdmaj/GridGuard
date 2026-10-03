import datetime
from typing import List, Dict
from simulator.plant import PhysicalPlant
from simulator.constants import SIMULATION_TIMESTEP_MINUTES

class SimulationRunner:
    def __init__(self, start_time: datetime.datetime = None) -> None:
        self.plant = PhysicalPlant()
        self.current_time = start_time if start_time else datetime.datetime(2026, 1, 1, 0, 0, 0)
        self.history: List[Dict] = []

    def run_step(self, battery_command_kw: float = 0.0) -> dict:
        self.plant.step(battery_command_kw)
        telemetry = self.plant.get_telemetry(self.current_time)
        self.history.append(telemetry)
        self.current_time += datetime.timedelta(minutes=SIMULATION_TIMESTEP_MINUTES)
        return telemetry
