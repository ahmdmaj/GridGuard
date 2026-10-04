import pytest
from simulator.runner import SimulationRunner
from digital_twin.twin import DigitalTwin, TwinEvent

def test_plant_to_twin_integration() -> None:
    # Step 1: Initialization
    runner = SimulationRunner()
    twin = DigitalTwin()
    
    # Step 2: Normal Operation
    telemetry = runner.run_step()
    twin.update(telemetry)
    
    assert twin.get_current_state().grid.is_available is True
    
    # Step 3: Introduce a Physical Fault
    runner.plant.grid.fail()
    telemetry = runner.run_step()
    twin.update(telemetry)
    
    # Step 4: Verify Twin Event Detection
    assert twin.get_current_state().grid.is_available is False
    assert len(twin.events) > 0
    assert twin.events[-1]["event"] == TwinEvent.GRID_FAILURE
    
    # Step 5: Physical Recovery
    runner.plant.grid.restore()
    telemetry = runner.run_step()
    twin.update(telemetry)
    
    # Step 6: Verify Twin Recovery Detection
    assert twin.get_current_state().grid.is_available is True
    assert len(twin.events) > 0
    assert twin.events[-1]["event"] == TwinEvent.GRID_RESTORED
