import pytest
from controller.engine import DecisionEngine
from simulator.constants import OperatingMode
from digital_twin.state import DigitalTwinState, GridState, SolarState, BatteryState, GeneratorState, LoadState

def test_decision_engine_grid_normal() -> None:
    engine = DecisionEngine()
    twin_state = DigitalTwinState(
        grid=GridState(is_available=True),
        battery=BatteryState(soc=100.0)
    )
    esh: dict = {}
    
    command = engine.evaluate(twin_state, esh, esh)
    
    assert engine.current_mode == OperatingMode.NORMAL
    assert command["battery_command_kw"] == 0.0
    assert command["generator_run"] is False

def test_decision_engine_grid_normal_charges_battery() -> None:
    engine = DecisionEngine()
    twin_state = DigitalTwinState(
        grid=GridState(is_available=True),
        battery=BatteryState(soc=50.0)
    )
    esh: dict = {}
    
    command = engine.evaluate(twin_state, esh, esh)
    
    assert engine.current_mode == OperatingMode.NORMAL
    assert command["battery_command_kw"] == -20.0
    assert command["generator_run"] is False
    assert "Charging battery" in command["decision_reason"]

def get_mock_failed_state(soc: float = 50.0) -> DigitalTwinState:
    return DigitalTwinState(
        grid=GridState(is_available=False),
        battery=BatteryState(soc=soc),
        solar=SolarState(power_kw=0.0),
        loads=LoadState(critical_kw=0.0, important_kw=0.0, flexible_kw=0.0)
    )

def test_decision_engine_grid_failed() -> None:
    engine = DecisionEngine()
    twin_state = get_mock_failed_state()
    esh: dict = {
        "all_loads_hours": 3.0,
        "critical_and_important_hours": 2.5,
        "critical_only_hours": 2.5
    }
    
    command = engine.evaluate(twin_state, esh)
    
    assert engine.current_mode == OperatingMode.GRID_FAILED
    assert command["battery_command_kw"] == 0.0
    assert command["generator_run"] is False
    assert command["connect_flexible"] is False

def test_engine_generator_hysteresis() -> None:
    engine = DecisionEngine()
    
    # Trigger start via poor ESH
    twin_state = get_mock_failed_state(soc=50.0)
    battery_only_esh = {"critical_only_hours": 1.0, "all_loads_hours": 1.0}
    command = engine.evaluate(twin_state, {}, battery_only_esh)
    assert command["generator_run"] is True
    
    # Hysteresis hold
    twin_state = get_mock_failed_state(soc=50.0)
    battery_only_esh = {"critical_only_hours": 5.0, "all_loads_hours": 5.0}
    command = engine.evaluate(twin_state, {}, battery_only_esh)
    assert command["generator_run"] is True 
    
    # Stop via SOC
    twin_state = get_mock_failed_state(soc=81.0)
    command = engine.evaluate(twin_state, {}, battery_only_esh)
    assert command["generator_run"] is False

def test_engine_defers_generator_if_solar_incoming() -> None:
    # Phase D Feature
    engine = DecisionEngine()
    twin_state = get_mock_failed_state(soc=25.0) 
    
    # Even though SOC is 25%, battery_only_esh says we have 10 hours of survival (solar incoming)
    battery_only_esh = {"critical_only_hours": 10.0, "all_loads_hours": 10.0}
    full_esh = battery_only_esh
    
    command = engine.evaluate(twin_state, full_esh, battery_only_esh)
    
    assert command["generator_run"] is False

def test_engine_starts_generator_if_forecast_poor() -> None:
    # Phase D Feature
    engine = DecisionEngine()
    twin_state = get_mock_failed_state(soc=40.0)
    
    # Even though SOC is 40% (high), battery_only_esh says we have 1.5 hours of survival (huge load incoming)
    battery_only_esh = {"critical_only_hours": 1.5, "all_loads_hours": 1.5}
    full_esh = {"critical_only_hours": 48.0, "all_loads_hours": 48.0} # Gen saves us
    
    command = engine.evaluate(twin_state, full_esh, battery_only_esh)
    
    assert command["generator_run"] is True

def test_engine_hard_soc_safety_net() -> None:
    # Phase D Feature
    engine = DecisionEngine()
    twin_state = get_mock_failed_state(soc=19.0) # Below hard start 20.0
    
    # Even if forecast is amazing, trigger generator because battery is dangerously low right now
    battery_only_esh = {"critical_only_hours": 100.0, "all_loads_hours": 100.0}
    
    command = engine.evaluate(twin_state, {}, battery_only_esh)
    
    assert command["generator_run"] is True

def test_engine_load_shedding_flexible_hysteresis() -> None:
    engine = DecisionEngine()
    twin_state = get_mock_failed_state(soc=50.0)
    
    # 1. Initial State: Healthy
    esh = {"all_loads_hours": 5.0, "critical_and_important_hours": 5.0, "critical_only_hours": 5.0}
    command = engine.evaluate(twin_state, esh, esh)
    assert command["connect_flexible"] is True
    
    # 2. Shedding triggers at 3.9
    esh = {"all_loads_hours": 3.9, "critical_and_important_hours": 4.5, "critical_only_hours": 5.0}
    command = engine.evaluate(twin_state, esh, esh)
    assert command["connect_flexible"] is False
    
    # 3. Forecast corruption triggers false rise, but NO reconnection
    esh = {"all_loads_hours": 6.0, "critical_and_important_hours": 6.0, "critical_only_hours": 6.5}
    command = engine.evaluate(twin_state, esh, esh)
    assert command["connect_flexible"] is False
    
    # 4. Valid reconnection triggered by critical_and_important_hours >= 8.0
    esh = {"all_loads_hours": 8.1, "critical_and_important_hours": 8.1, "critical_only_hours": 8.5}
    command = engine.evaluate(twin_state, esh, esh)
    assert command["connect_flexible"] is True

def test_engine_load_shedding_important_hysteresis() -> None:
    engine = DecisionEngine()
    twin_state = get_mock_failed_state(soc=50.0)
    
    # 1. Start with flexible already shed (e.g., ESH is 3.0)
    esh = {"all_loads_hours": 3.0, "critical_and_important_hours": 3.0, "critical_only_hours": 5.0}
    command = engine.evaluate(twin_state, esh, esh)
    assert command["connect_flexible"] is False
    assert command["connect_important"] is True
    
    # 2. Shed important at 1.9
    esh = {"all_loads_hours": 1.9, "critical_and_important_hours": 1.9, "critical_only_hours": 3.5}
    command = engine.evaluate(twin_state, esh, esh)
    assert command["connect_important"] is False
    
    # 3. No reconnection at 5.0
    esh = {"all_loads_hours": 5.0, "critical_and_important_hours": 5.0, "critical_only_hours": 5.0}
    command = engine.evaluate(twin_state, esh, esh)
    assert command["connect_important"] is False
    
    # 4. Valid reconnection triggered by critical_only_hours >= 6.0
    esh = {"all_loads_hours": 6.1, "critical_and_important_hours": 6.1, "critical_only_hours": 6.1}
    command = engine.evaluate(twin_state, esh, esh)
    assert command["connect_important"] is True

def test_grid_restore_reconnects_all_loads() -> None:
    engine = DecisionEngine()
    
    # Force shedding
    twin_state = get_mock_failed_state(soc=50.0)
    esh = {"all_loads_hours": 1.0, "critical_and_important_hours": 1.0, "critical_only_hours": 1.0}
    command = engine.evaluate(twin_state, esh, esh)
    assert command["connect_flexible"] is False
    assert command["connect_important"] is False
    
    # Grid restores
    twin_state.grid.is_available = True
    command = engine.evaluate(twin_state, esh, esh) # ESH doesn't matter now
    assert command["connect_flexible"] is True
    assert command["connect_important"] is True

def test_battery_command_generator_off_covers_deficit() -> None:
    engine = DecisionEngine()
    twin_state = get_mock_failed_state(soc=50.0)
    twin_state.solar.power_kw = 2.0
    twin_state.loads.critical_kw = 4.0
    twin_state.loads.important_kw = 4.0
    twin_state.loads.flexible_kw = 0.0
    
    esh = {"all_loads_hours": 3.0, "critical_and_important_hours": 2.5, "critical_only_hours": 5.0}
    command = engine.evaluate(twin_state, esh, esh)
    
    assert command["generator_run"] is False
    assert command["battery_command_kw"] == 6.0
    
    twin_state.solar.power_kw = 10.0
    command = engine.evaluate(twin_state, esh, esh)
    assert command["battery_command_kw"] == -2.0

def test_battery_command_generator_on_covers_deficit_and_charges() -> None:
    engine = DecisionEngine()
    twin_state = get_mock_failed_state(soc=10.0)
    twin_state.solar.power_kw = 0.0
    twin_state.loads.critical_kw = 10.0
    twin_state.loads.important_kw = 0.0
    twin_state.loads.flexible_kw = 0.0
    
    esh = {"all_loads_hours": 5.0, "critical_and_important_hours": 5.0, "critical_only_hours": 5.0}
    command = engine.evaluate(twin_state, esh, esh)
    
    assert command["generator_run"] is True
    assert command["battery_command_kw"] == -5.0

def test_battery_command_generator_on_load_exceeds_gen() -> None:
    engine = DecisionEngine()
    twin_state = get_mock_failed_state(soc=10.0)
    twin_state.solar.power_kw = 0.0
    twin_state.loads.critical_kw = 20.0
    twin_state.loads.important_kw = 0.0
    twin_state.loads.flexible_kw = 0.0
    
    esh = {"all_loads_hours": 5.0, "critical_and_important_hours": 5.0, "critical_only_hours": 5.0}
    command = engine.evaluate(twin_state, esh, esh)
    
    assert command["generator_run"] is True
    assert command["battery_command_kw"] == 5.0

def test_engine_config_overrides() -> None:
    custom_config = {
        "generator_capacity_kw": 20.0,
        "hard_start_soc": 40.0,
        "generator_stop_soc": 90.0,
        "target_soc": 90.0
    }
    engine = DecisionEngine(config=custom_config)
    
    # Test custom start SOC
    twin_state = get_mock_failed_state(soc=35.0) # Below 40
    esh = {"all_loads_hours": 5.0, "critical_and_important_hours": 5.0, "critical_only_hours": 5.0}
    command = engine.evaluate(twin_state, esh, esh)
    assert command["generator_run"] is True
    
    # Test custom generator capacity
    twin_state.loads.critical_kw = 10.0
    command = engine.evaluate(twin_state, esh, esh)
    # active_load = 10.0, deficit = 10.0
    # battery_command = deficit - 20.0 = -10.0 (Charge at 10kW)
    assert command["battery_command_kw"] == -10.0

    # Test custom target SOC
    twin_state_grid = DigitalTwinState(
        grid=GridState(is_available=True),
        battery=BatteryState(soc=95.0) # Above custom target 90.0
    )
    command_grid = engine.evaluate(twin_state_grid, esh, esh)
    assert command_grid["battery_command_kw"] == 0.0

def test_engine_instantaneous_peak_demand() -> None:
    engine = DecisionEngine()
    engine.generator_requested = True # Simulate generator running
    
    twin_state = DigitalTwinState(
        grid=GridState(is_available=False),
        battery=BatteryState(soc=50.0),
        solar=SolarState(power_kw=0.0),
        generator=GeneratorState(is_available=True, power_kw=15.0),
        loads=LoadState(critical_kw=10.0, important_kw=15.0, flexible_kw=20.0)
    )
    
    # ESH is extremely high, should normally not shed loads
    esh = {"all_loads_hours": 100.0, "critical_and_important_hours": 100.0, "critical_only_hours": 100.0}
    
    command = engine.evaluate(twin_state, esh, esh)
    
    # Total demand = 45 kW. Max supply = 0 (solar) + 20 (battery) + 15 (gen) = 35 kW.
    # Instantaneous limit is exceeded.
    # Critical + Important = 10 + 15 = 25 kW <= 35 kW.
    # Therefore, flexible should be shed.
    assert command["connect_flexible"] is False
    assert command["connect_important"] is True
    assert command["connect_critical"] is True
    assert engine.current_mode == OperatingMode.GRID_FAILED
    assert "Peak demand exceeded supply" in command["decision_reason"]
