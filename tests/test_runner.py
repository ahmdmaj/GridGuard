import datetime
from simulator.runner import SimulationRunner

def test_runner_initialization():
    start = datetime.datetime(2026, 1, 1, 12, 0, 0)
    runner = SimulationRunner(start_time=start)
    assert runner.current_time == start
    assert len(runner.history) == 0

def test_runner_run_step_advances_clock():
    start = datetime.datetime(2026, 1, 1, 12, 0, 0)
    runner = SimulationRunner(start_time=start)
    
    telemetry = runner.run_step()
    
    assert runner.current_time == datetime.datetime(2026, 1, 1, 12, 5, 0)
    assert len(runner.history) == 1
    
    expected_keys = {
        "timestamp", "grid_available", "grid_voltage", "solar_kw", 
        "battery_soc", "battery_kw", "generator_kw", "generator_fuel_liters", 
        "load_critical_kw", "load_important_kw", "load_flexible_kw", "unserved_kw"
    }
    assert expected_keys.issubset(telemetry.keys())

def test_runner_consecutive_steps():
    start = datetime.datetime(2026, 1, 1, 12, 0, 0)
    runner = SimulationRunner(start_time=start)
    
    runner.run_step()
    runner.run_step()
    runner.run_step()
    
    assert runner.current_time == datetime.datetime(2026, 1, 1, 12, 15, 0)
    assert len(runner.history) == 3
