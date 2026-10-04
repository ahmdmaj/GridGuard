import json
import copy
from typing import Tuple, Dict, Any, List
from simulator.runner import SimulationRunner
from simulator.constants import LoadCategory
from digital_twin.twin import DigitalTwin
from controller.baseline import BaselineController
from controller.engine import DecisionEngine
from forecasting.service import ForecastService
from metrics.esh import ESHCalculator
from metrics.collector import MetricsCollector

class ExperimentRunner:
    def __init__(self, start_soc_kwh: float = 15.0) -> None:
        self.start_soc_kwh = start_soc_kwh

    def run_scenario(self, controller_type: str) -> Tuple[Dict[str, float], List[Dict[str, Any]]]:
        runner = SimulationRunner()
        runner.plant.battery.current_energy_kwh = self.start_soc_kwh
        twin = DigitalTwin()

        if controller_type == "baseline":
            controller = BaselineController()
        elif controller_type == "gridguard":
            controller = DecisionEngine()
            forecast_service = ForecastService()
            esh_calc = ESHCalculator()
        else:
            raise ValueError(f"Unknown controller_type: {controller_type}")

        simulation_steps = 144

        for step in range(simulation_steps):
            # A. Scenario Injection
            if step == 12:
                runner.plant.grid.fail()
                runner.plant.solar.set_availability(0.0)
            if step == 120:
                runner.plant.grid.restore()
                runner.plant.solar.set_availability(0.5)

            # B. Telemetry & Twin
            current_telemetry = runner.plant.get_telemetry(runner.current_time)
            twin.update(current_telemetry)

            # C. Intelligence (GridGuard only)
            if controller_type == "gridguard":
                fc = forecast_service.generate_forecast(current_telemetry, 12)
                twin_state = twin.get_current_state()
                full_esh = esh_calc.calculate_forecast_esh(twin_state, fc)
                
                twin_no_gen = copy.deepcopy(twin_state)
                twin_no_gen["generator_state"]["is_available"] = False
                battery_only_esh = esh_calc.calculate_forecast_esh(twin_no_gen, fc)
            else:
                full_esh = {}
                battery_only_esh = {}

            # D. Controller Command
            if controller_type == "baseline":
                cmd = controller.evaluate(twin.get_current_state())
            elif controller_type == "gridguard":
                cmd = controller.evaluate(twin.get_current_state(), full_esh, battery_only_esh)

            # E. Actuate Physical Plant
            runner.plant.load.set_connection(LoadCategory.CRITICAL, cmd["connect_critical"])
            runner.plant.load.set_connection(LoadCategory.IMPORTANT, cmd["connect_important"])
            runner.plant.load.set_connection(LoadCategory.FLEXIBLE, cmd["connect_flexible"])

            if cmd["generator_run"]:
                runner.plant.generator.start()
            else:
                runner.plant.generator.stop()

            # F. Step Time Forward
            runner.run_step(battery_command_kw=cmd["battery_command_kw"])

        # Post-Loop
        metrics = MetricsCollector().calculate_metrics(runner.history)
        return metrics, runner.history
