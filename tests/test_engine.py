import pytest
from controller.engine import DecisionEngine
from simulator.constants import OperatingMode

def test_decision_engine_grid_normal() -> None:
    engine = DecisionEngine()
    twin_state = {
        "grid_state": {"is_available": True}
    }
    esh: dict = {}
    
    command = engine.evaluate(twin_state, esh)
    
    assert engine.current_mode == OperatingMode.NORMAL
    assert command["battery_command_kw"] == 0.0
    assert command["generator_run"] is False
    assert command["connect_critical"] is True
    assert command["connect_important"] is True
    assert command["connect_flexible"] is True
    assert "Grid is available" in command["decision_reason"]

def get_mock_failed_state(soc: float = 50.0) -> dict:
    return {
        "grid_state": {"is_available": False},
        "battery_state": {"soc": soc},
        "solar_state": {"generation_kw": 0.0},
        "load_state": {
            "critical_kw": 0.0,
            "important_kw": 0.0,
            "flexible_kw": 0.0
        }
    }

def test_decision_engine_grid_failed() -> None:
    engine = DecisionEngine()
    twin_state = get_mock_failed_state()
    esh: dict = {
        "all_loads_hours": 3.0,
        "critical_and_important_hours": 2.5
    }
    
    command = engine.evaluate(twin_state, esh)
    
    assert engine.current_mode == OperatingMode.GRID_FAILED
    assert command["battery_command_kw"] == 0.0
    assert command["generator_run"] is False
    assert command["connect_critical"] is True
    assert command["connect_important"] is True
    assert command["connect_flexible"] is False
    assert "Grid failed. ESH declining. Shedding flexible loads." in command["decision_reason"]

def test_engine_generator_hysteresis() -> None:
    engine = DecisionEngine()
    
    # SOC = 29.0, ESH safe
    twin_state = get_mock_failed_state(soc=29.0)
    esh = {"all_loads_hours": 5.0, "critical_and_important_hours": 5.0}
    command = engine.evaluate(twin_state, esh)
    assert command["generator_run"] is True
    
    # SOC = 50.0, ESH safe
    twin_state = get_mock_failed_state(soc=50.0)
    command = engine.evaluate(twin_state, esh)
    assert command["generator_run"] is True  # Hysteresis hold
    
    # SOC = 81.0, ESH safe
    twin_state = get_mock_failed_state(soc=81.0)
    command = engine.evaluate(twin_state, esh)
    assert command["generator_run"] is False

def test_engine_esh_load_shedding() -> None:
    engine = DecisionEngine()
    twin_state = get_mock_failed_state(soc=50.0)
    
    # ESH all_loads_hours = 5.0
    esh = {"all_loads_hours": 5.0, "critical_and_important_hours": 5.0}
    command = engine.evaluate(twin_state, esh)
    assert command["connect_flexible"] is True
    assert engine.current_mode == OperatingMode.GRID_FAILED
    
    # ESH all_loads_hours = 3.0, critical_and_important_hours = 2.5
    esh = {"all_loads_hours": 3.0, "critical_and_important_hours": 2.5}
    command = engine.evaluate(twin_state, esh)
    assert command["connect_flexible"] is False
    assert command["connect_important"] is True
    assert engine.current_mode == OperatingMode.GRID_FAILED
    
    # ESH critical_and_important_hours = 1.5
    esh = {"all_loads_hours": 1.0, "critical_and_important_hours": 1.5}
    command = engine.evaluate(twin_state, esh)
    assert command["connect_flexible"] is False
    assert command["connect_important"] is False
    assert command["connect_critical"] is True
    assert engine.current_mode == OperatingMode.ENERGY_SCARCITY

def test_engine_battery_command_calculation() -> None:
    engine = DecisionEngine()
    twin_state = get_mock_failed_state(soc=50.0)
    twin_state["solar_state"]["generation_kw"] = 2.0
    twin_state["load_state"]["critical_kw"] = 4.0
    twin_state["load_state"]["important_kw"] = 4.0
    twin_state["load_state"]["flexible_kw"] = 0.0
    
    # Loads retained total 8.0 kW (critical + important)
    esh = {"all_loads_hours": 3.0, "critical_and_important_hours": 2.5}
    command = engine.evaluate(twin_state, esh)
    # deficit = 8.0 - 2.0 = 6.0
    assert command["battery_command_kw"] == 6.0
    
    # Solar = 10.0, loads = 8.0 kW
    twin_state["solar_state"]["generation_kw"] = 10.0
    command = engine.evaluate(twin_state, esh)
    # deficit = 8.0 - 10.0 = -2.0
    assert command["battery_command_kw"] == -2.0
