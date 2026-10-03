import pytest
import math
from metrics.esh import ESHCalculator

def get_base_twin_state() -> dict:
    return {
        "solar_state": {"generation_kw": 0.0},
        "battery_state": {"soc": 0.0},
        "generator_state": {"fuel_liters": 0.0},
        "load_state": {
            "critical_kw": 0.0,
            "important_kw": 0.0,
            "flexible_kw": 0.0
        }
    }

def test_infinite_horizon() -> None:
    calc = ESHCalculator()
    state = get_base_twin_state()
    state["solar_state"]["generation_kw"] = 10.0
    state["load_state"]["critical_kw"] = 4.0
    state["load_state"]["important_kw"] = 3.0
    state["load_state"]["flexible_kw"] = 2.0  # Total 9.0

    result = calc.calculate_instantaneous_esh(state)
    
    assert math.isinf(result["critical_only_hours"])
    assert math.isinf(result["critical_and_important_hours"])
    assert math.isinf(result["all_loads_hours"])

def test_battery_only_no_gen() -> None:
    calc = ESHCalculator()
    state = get_base_twin_state()
    state["battery_state"]["soc"] = 100.0
    # Usable SOC = 80%, 40 kWh total -> 32 kWh usable
    state["load_state"]["critical_kw"] = 4.0
    state["load_state"]["important_kw"] = 3.0
    state["load_state"]["flexible_kw"] = 3.0  # Total 10.0

    result = calc.calculate_instantaneous_esh(state)
    
    # 32 / 10 = 3.2 hours
    assert result["all_loads_hours"] == 3.2

def test_battery_and_gen() -> None:
    calc = ESHCalculator()
    state = get_base_twin_state()
    state["battery_state"]["soc"] = 100.0  # 32 kWh usable
    state["generator_state"]["fuel_liters"] = 30.0  # 30 / 0.3 = 100 kWh usable
    # Total available = 132 kWh
    state["load_state"]["critical_kw"] = 3.0

    result = calc.calculate_instantaneous_esh(state)
    
    # 132 / 3.0 = 44.0 hours
    assert result["critical_only_hours"] == 44.0

def test_forecast_esh_exhaustion() -> None:
    calc = ESHCalculator()
    # Provide a twin_state with 5.0 kWh of total available energy.
    state = get_base_twin_state()
    state["battery_state"]["soc"] = 32.5  # (32.5 - 20) / 100 * 40 = 5.0 kWh usable
    
    forecast = [
        {"solar_kw": 0.0, "load_critical_kw": 12.0, "load_important_kw": 0.0, "load_flexible_kw": 0.0},
        {"solar_kw": 0.0, "load_critical_kw": 12.0, "load_important_kw": 0.0, "load_flexible_kw": 0.0},
        {"solar_kw": 0.0, "load_critical_kw": 12.0, "load_important_kw": 0.0, "load_flexible_kw": 0.0},
    ]
    
    result = calc.calculate_forecast_esh(state, forecast)
    
    # 5.0 / 12.0 = 0.41666... hours
    assert math.isclose(result["all_loads_hours"], 5.0 / 12.0)

def test_forecast_esh_survival() -> None:
    calc = ESHCalculator()
    state = get_base_twin_state()
    state["battery_state"]["soc"] = 45.0  # (45 - 20) / 100 * 40 = 10.0 kWh usable
    
    forecast = [
        {"solar_kw": 5.0, "load_critical_kw": 5.0, "load_important_kw": 0.0, "load_flexible_kw": 0.0},
        {"solar_kw": 5.0, "load_critical_kw": 5.0, "load_important_kw": 0.0, "load_flexible_kw": 0.0},
        {"solar_kw": 5.0, "load_critical_kw": 5.0, "load_important_kw": 0.0, "load_flexible_kw": 0.0},
    ]
    
    result = calc.calculate_forecast_esh(state, forecast)
    
    assert math.isinf(result["critical_only_hours"])
