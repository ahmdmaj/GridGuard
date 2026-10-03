import pytest
from controller.baseline import BaselineController

def get_mock_twin_state(soc: float, is_grid_available: bool = False) -> dict:
    return {
        "grid_state": {"is_available": is_grid_available},
        "battery_state": {"soc": soc},
        "solar_state": {"generation_kw": 2.0},
        "load_state": {
            "critical_kw": 4.0,
            "important_kw": 3.0,
            "flexible_kw": 2.0
        }
    }

def test_baseline_grid_normal() -> None:
    controller = BaselineController()
    state = get_mock_twin_state(100.0, is_grid_available=True)
    command = controller.evaluate(state)
    
    assert command["generator_run"] is False
    assert command["connect_flexible"] is True
    assert command["battery_command_kw"] == 0.0

def test_baseline_grid_failed_high_soc() -> None:
    controller = BaselineController()
    state = get_mock_twin_state(50.0)
    command = controller.evaluate(state)
    
    assert command["generator_run"] is True
    assert command["connect_critical"] is True
    assert command["connect_important"] is True
    assert command["connect_flexible"] is False
    # Active = 4.0 + 3.0 = 7.0, Solar = 2.0, Deficit = 5.0
    assert command["battery_command_kw"] == 5.0
    assert "shedding flexible" in command["decision_reason"]

def test_baseline_grid_failed_low_soc() -> None:
    controller = BaselineController()
    state = get_mock_twin_state(15.0)
    command = controller.evaluate(state)
    
    assert command["generator_run"] is True
    assert command["connect_critical"] is True
    assert command["connect_important"] is False
    assert command["connect_flexible"] is False
    # Active = 4.0, Solar = 2.0, Deficit = 2.0
    assert command["battery_command_kw"] == 2.0
    assert "shedding important and flexible" in command["decision_reason"]
