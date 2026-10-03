import pytest
from telemetry.broker import MockMQTTBroker
from telemetry.nodes import EdgePlantNode, CloudControllerNode
from simulator.runner import SimulationRunner
from digital_twin.twin import DigitalTwin
from controller.engine import DecisionEngine
from forecasting.service import ForecastService
from metrics.esh import ESHCalculator

def test_pubsub_control_loop() -> None:
    broker = MockMQTTBroker()
    runner = SimulationRunner()
    twin = DigitalTwin()
    controller = DecisionEngine()
    forecast_service = ForecastService()
    esh_calc = ESHCalculator()

    plant_node = EdgePlantNode(runner, broker)
    cloud_node = CloudControllerNode(controller, twin, forecast_service, esh_calc, broker)

    # Calling tick should synchronously trigger the loop
    # telemetry published -> cloud node receives -> controller evaluates -> command published -> plant node receives
    telemetry = plant_node.tick()
    
    assert plant_node.latest_command is not None
    assert "battery_command_kw" in plant_node.latest_command
    assert "generator_run" in plant_node.latest_command
    assert "connect_critical" in plant_node.latest_command
    assert "connect_important" in plant_node.latest_command
    assert "connect_flexible" in plant_node.latest_command
