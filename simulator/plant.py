import datetime
from simulator.grid import Grid
from simulator.solar import SolarPV
from simulator.battery import Battery
from simulator.generator import Generator
from simulator.load import BuildingLoad
from simulator.constants import LoadCategory

class PhysicalPlant:
    def __init__(self) -> None:
        self.grid = Grid()
        self.solar = SolarPV()
        self.battery = Battery()
        self.generator = Generator()
        self.load = BuildingLoad()

        self.current_grid_kw: float = 0.0
        self.current_solar_kw: float = 0.0
        self.current_batt_kw: float = 0.0
        self.current_gen_kw: float = 0.0
        self.current_load_kw: float = 0.0
        self.current_unserved_kw: float = 0.0

    def step(self, battery_command_kw: float = 0.0) -> None:
        load_kw = -self.load.get_total_demand_kw()
        solar_kw = self.solar.get_generation()

        if battery_command_kw > 0:
            batt_kw = self.battery.discharge(battery_command_kw)
        elif battery_command_kw < 0:
            batt_kw = -self.battery.charge(abs(battery_command_kw))
        else:
            batt_kw = 0.0

        balance = load_kw + solar_kw + batt_kw

        if balance < 0 and self.generator.is_running:
            gen_kw = self.generator.generate(abs(balance))
            balance += gen_kw
        else:
            gen_kw = self.generator.generate(0.0)

        if self.grid.is_available:
            grid_kw = -balance
            balance += grid_kw
        else:
            grid_kw = 0.0

        if balance < 0:
            unserved_kw = abs(balance)
        else:
            unserved_kw = 0.0

        self.current_grid_kw = grid_kw
        self.current_solar_kw = solar_kw
        self.current_batt_kw = batt_kw
        self.current_gen_kw = gen_kw
        self.current_load_kw = load_kw
        self.current_unserved_kw = unserved_kw

    def get_telemetry(self, current_time: datetime.datetime) -> dict:
        return {
            "timestamp": current_time.isoformat() + "Z",
            "grid_available": self.grid.is_available,
            "grid_voltage": self.grid.voltage,
            "solar_kw": self.current_solar_kw,
            "battery_soc": self.battery.soc,
            "battery_kw": self.current_batt_kw,
            "generator_kw": self.current_gen_kw,
            "generator_fuel_liters": self.generator.fuel_liters,
            "generator_available": self.generator.is_available,
            "load_critical_kw": self.load.get_demand_by_category(LoadCategory.CRITICAL),
            "load_important_kw": self.load.get_demand_by_category(LoadCategory.IMPORTANT),
            "load_flexible_kw": self.load.get_demand_by_category(LoadCategory.FLEXIBLE),
            "unserved_kw": self.current_unserved_kw
        }
