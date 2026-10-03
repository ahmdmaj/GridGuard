from typing import Dict, Any
from simulator.runner import SimulationRunner
from digital_twin.twin import DigitalTwin
from controller.engine import DecisionEngine
from forecasting.service import ForecastService
from metrics.esh import ESHCalculator
from metrics.collector import MetricsCollector
from telemetry.broker import MockMQTTBroker
from telemetry.nodes import EdgePlantNode, CloudControllerNode
from simulator.constants import LoadCategory

class DisasterOrchestrator:
    def run_disaster(self, disaster_name: str) -> Dict[str, float]:
        broker = MockMQTTBroker()
        runner = SimulationRunner()
        twin = DigitalTwin()
        controller = DecisionEngine()
        forecast = ForecastService()
        esh = ESHCalculator()
        
        edge = EdgePlantNode(runner, broker)
        cloud = CloudControllerNode(controller, twin, forecast, esh, broker)
        
        runner.plant.battery.current_energy_kwh = 15.0
        simulation_steps = 144
        
        for step in range(simulation_steps):
            # Base Fault
            if step == 12:
                runner.plant.grid.fail()
            if step == 120:
                runner.plant.grid.restore()
                
            # Disaster Injection
            if disaster_name == "solar_scarcity":
                runner.plant.solar.set_availability(0.1)
                
            if disaster_name == "generator_failure":
                if step == 36:
                    runner.plant.generator.set_availability(False)
                    
            if disaster_name == "comms_blackout":
                if step == 36:
                    broker.subscribers["gridguard/controller/command"] = []
                if step == 72:
                    broker.subscribe("gridguard/controller/command", edge._on_command_received)
                    
            edge.tick()
            
        metrics = MetricsCollector().calculate_metrics(runner.history)
        return metrics
