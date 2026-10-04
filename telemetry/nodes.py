import json
import copy
from typing import Optional, Dict, Any
from telemetry.broker import MockMQTTBroker, TOPIC_TELEMETRY, TOPIC_COMMAND
from simulator.runner import SimulationRunner
from simulator.constants import LoadCategory
from digital_twin.twin import DigitalTwin
from controller.engine import DecisionEngine
from forecasting.service import ForecastService
from metrics.esh import ESHCalculator
from controller.command import SystemCommand

class EdgePlantNode:
    def __init__(self, runner: SimulationRunner, broker: MockMQTTBroker) -> None:
        self.runner = runner
        self.broker = broker
        self.latest_command: Optional[SystemCommand] = None
        self.broker.subscribe(TOPIC_COMMAND, self._on_command_received)

    def _on_command_received(self, payload_str: str) -> None:
        self.latest_command = json.loads(payload_str)

    def tick(self) -> Dict[str, Any]:
        battery_command_kw = 0.0

        if self.latest_command is not None:
            self.runner.plant.load.set_connection(LoadCategory.CRITICAL, self.latest_command.get("connect_critical", True))
            self.runner.plant.load.set_connection(LoadCategory.IMPORTANT, self.latest_command.get("connect_important", True))
            self.runner.plant.load.set_connection(LoadCategory.FLEXIBLE, self.latest_command.get("connect_flexible", True))
            
            if self.latest_command.get("generator_run", False):
                self.runner.plant.generator.start()
            else:
                self.runner.plant.generator.stop()
                
            battery_command_kw = self.latest_command.get("battery_command_kw", 0.0)

        telemetry = self.runner.run_step(battery_command_kw)
        self.broker.publish(TOPIC_TELEMETRY, telemetry)
        return telemetry

class CloudControllerNode:
    def __init__(self, controller: DecisionEngine, twin: DigitalTwin, forecast_service: ForecastService, esh_calc: ESHCalculator, broker: MockMQTTBroker) -> None:
        self.controller = controller
        self.twin = twin
        self.forecast_service = forecast_service
        self.esh_calc = esh_calc
        self.broker = broker
        self.broker.subscribe(TOPIC_TELEMETRY, self._on_telemetry_received)

    def _on_telemetry_received(self, payload_str: str) -> None:
        telemetry = json.loads(payload_str)
        self.twin.update(telemetry)
        
        twin_state = self.twin.get_current_state()
        fc = self.forecast_service.generate_forecast(telemetry, 12)
        
        full_esh = self.esh_calc.calculate_forecast_esh(twin_state, fc)
        
        twin_no_gen = copy.deepcopy(twin_state)
        twin_no_gen["generator_state"]["is_available"] = False
        battery_only_esh = self.esh_calc.calculate_forecast_esh(twin_no_gen, fc)
        
        cmd = self.controller.evaluate(twin_state, full_esh, battery_only_esh)
        self.broker.publish(TOPIC_COMMAND, cmd)
