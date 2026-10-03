import time
from simulator.runner import SimulationRunner
from digital_twin.twin import DigitalTwin
from controller.engine import DecisionEngine
from forecasting.service import ForecastService
from metrics.esh import ESHCalculator
from telemetry.broker import MockMQTTBroker
from telemetry.nodes import EdgePlantNode, CloudControllerNode
from ui.dashboard import Dashboard

def main() -> None:
    broker = MockMQTTBroker()
    runner = SimulationRunner()
    twin = DigitalTwin()
    controller = DecisionEngine()
    forecast = ForecastService()
    esh_calc = ESHCalculator()
    
    edge = EdgePlantNode(runner, broker)
    cloud = CloudControllerNode(controller, twin, forecast, esh_calc, broker)
    
    runner.plant.battery.current_energy_kwh = 25.0
    
    for step in range(73):
        if step == 10:
            runner.plant.grid.fail()
            runner.plant.solar.set_availability(0.0)
        if step == 50:
            runner.plant.grid.restore()
            runner.plant.solar.set_availability(0.5)
            
        telemetry = edge.tick()
        twin_state = twin.get_current_state()
        fc = forecast.generate_forecast(telemetry, 12)
        esh = esh_calc.calculate_forecast_esh(twin_state, fc)
        cmd = edge.latest_command if edge.latest_command else {}
        
        Dashboard.render(step, telemetry, twin_state, esh, cmd)
        time.sleep(0.1)

if __name__ == "__main__":
    main()
