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

def test_baseline_grid_normal_charges_battery() -> None:
    controller = BaselineController()
    
    # Needs charge
    state = get_mock_twin_state(50.0, is_grid_available=True)
    command = controller.evaluate(state)
    assert command["generator_run"] is False
    assert command["connect_flexible"] is True
    assert command["battery_command_kw"] == -20.0
    
    # Floating
    state = get_mock_twin_state(100.0, is_grid_available=True)
    command = controller.evaluate(state)
    assert command["battery_command_kw"] == 0.0

def test_baseline_battery_command_accounts_for_generator() -> None:
    controller = BaselineController()
    state = get_mock_twin_state(80.0) # High SOC, all connected
    command = controller.evaluate(state)
    
    assert command["generator_run"] is True
    assert command["connect_flexible"] is True
    
    # Active = 4 + 3 + 2 = 9.0
    # Solar = 2.0
    # Generator = 15.0
    # Command = 9.0 - 2.0 - 15.0 = -8.0 (Charging!)
    assert command["battery_command_kw"] == -8.0

def test_baseline_soc_hysteresis() -> None:
    controller = BaselineController()
    
    # Starts at 100%
    state = get_mock_twin_state(100.0)
    command = controller.evaluate(state)
    assert command["connect_flexible"] is True
    assert command["connect_important"] is True
    
    # Drops to 49.9 -> sheds flexible
    state = get_mock_twin_state(49.9)
    command = controller.evaluate(state)
    assert command["connect_flexible"] is False
    assert command["connect_important"] is True
    
    # Rises to 60.0 -> flexible stays shed (hysteresis)
    state = get_mock_twin_state(60.0)
    command = controller.evaluate(state)
    assert command["connect_flexible"] is False
    
    # Drops to 19.9 -> sheds important
    state = get_mock_twin_state(19.9)
    command = controller.evaluate(state)
    assert command["connect_flexible"] is False
    assert command["connect_important"] is False
    
    # Rises to 40.0 -> reconnects important, flexible still shed
    state = get_mock_twin_state(40.0)
    command = controller.evaluate(state)
    assert command["connect_important"] is True
    assert command["connect_flexible"] is False
    
    # Rises to 70.0 -> reconnects flexible
    state = get_mock_twin_state(70.0)
    command = controller.evaluate(state)
    assert command["connect_flexible"] is True
    assert command["connect_important"] is True
