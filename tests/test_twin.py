import pytest
from digital_twin.twin import DigitalTwin, TwinEvent
from simulator.telemetry import TelemetrySnapshot

def test_digital_twin_initial_state() -> None:
    twin = DigitalTwin()
    
    assert twin.state.timestamp == ""
    assert twin.state.grid.is_available is True
    assert twin.state.solar.power_kw == 0.0
    assert twin.state.battery.soc == 100.0
    assert twin.state.battery.power_kw == 0.0
    assert twin.state.generator.power_kw == 0.0
    assert twin.state.generator.fuel_liters == 100.0
    assert twin.state.generator.is_available is True
    assert twin.state.loads.critical_kw == 0.0
    
    current_state = twin.get_current_state()
    assert current_state.timestamp == ""
    assert current_state.grid.is_available is True
    assert current_state.solar.power_kw == 0.0
    assert current_state.battery.soc == 100.0
    assert current_state.generator.power_kw == 0.0
    assert current_state.loads.critical_kw == 0.0

def test_digital_twin_update() -> None:
    twin = DigitalTwin()
    mock_telemetry: TelemetrySnapshot = {
        "timestamp": "2023-10-27T10:00:00Z",
        "grid_available": True,
        "grid_voltage": 220.5,
        "solar_kw": 15.0,
        "battery_soc": 85.5,
        "battery_kw": -5.0,
        "generator_kw": 0.0,
        "generator_fuel_liters": 500.0,
        "generator_available": True,
        "load_critical_kw": 5.0,
        "load_important_kw": 3.0,
        "load_flexible_kw": 2.0,
        "unserved_kw": 0.0
    }
    
    twin.update(mock_telemetry)
    
    current_state = twin.get_current_state()
    
    assert current_state.timestamp == "2023-10-27T10:00:00Z"
    assert current_state.grid.is_available is True
    assert current_state.grid.voltage_pu == 220.5
    assert current_state.solar.power_kw == 15.0
    assert current_state.battery.soc == 85.5
    assert current_state.battery.power_kw == -5.0
    assert current_state.generator.power_kw == 0.0
    assert current_state.generator.fuel_liters == 500.0
    assert current_state.generator.is_available is True
    assert current_state.loads.critical_kw == 5.0
    assert current_state.loads.important_kw == 3.0
    assert current_state.loads.flexible_kw == 2.0
    
    assert len(twin.history) == 1
    assert twin.history[0].timestamp == "2023-10-27T10:00:00Z"

def test_digital_twin_event_detection() -> None:
    twin = DigitalTwin()
    
    # Snapshot 1: Normal
    telemetry_1: TelemetrySnapshot = {
        "timestamp": "T1",
        "grid_available": True, "grid_voltage": 220.0,
        "solar_kw": 0.0,
        "battery_soc": 100.0, "battery_kw": 0.0,
        "generator_kw": 0.0, "generator_fuel_liters": 100.0, "generator_available": True,
        "load_critical_kw": 0.0, "load_important_kw": 0.0, "load_flexible_kw": 0.0, "unserved_kw": 0.0
    }
    twin.update(telemetry_1)
    
    # Snapshot 2: Grid Failure
    telemetry_2 = telemetry_1.copy()
    telemetry_2["timestamp"] = "T2"
    telemetry_2["grid_available"] = False
    twin.update(telemetry_2)
    
    assert any(e["event"] == TwinEvent.GRID_FAILURE for e in twin.events)
    
    # Snapshot 3: Grid Restored
    telemetry_3 = telemetry_2.copy()
    telemetry_3["timestamp"] = "T3"
    telemetry_3["grid_available"] = True
    twin.update(telemetry_3)
    
    assert any(e["event"] == TwinEvent.GRID_RESTORED for e in twin.events)

def test_digital_twin_history_limit() -> None:
    twin = DigitalTwin()
    
    base_telemetry: TelemetrySnapshot = {
        "timestamp": "T0",
        "grid_available": True, "grid_voltage": 220.0,
        "solar_kw": 0.0,
        "battery_soc": 100.0, "battery_kw": 0.0,
        "generator_kw": 0.0, "generator_fuel_liters": 100.0, "generator_available": True,
        "load_critical_kw": 0.0, "load_important_kw": 0.0, "load_flexible_kw": 0.0, "unserved_kw": 0.0
    }
    
    for i in range(105):
        t = base_telemetry.copy()
        t["timestamp"] = f"T{i}"
        twin.update(t)
        
    assert len(twin.history) == 100
