import pytest
from metrics.esh import ESHCalculator
from digital_twin.state import DigitalTwinState, BatteryState, GeneratorState

def test_esh_constant_load_no_solar() -> None:
    esh = ESHCalculator({"simulation_timestep_minutes": 5.0})
    state = DigitalTwinState(
        battery=BatteryState(soc=100.0),
        generator=GeneratorState(fuel_liters=0.0, is_available=False)
    )
    forecast = [{"load_critical_kw": 10.0, "load_important_kw": 0.0, "load_flexible_kw": 0.0, "solar_kw": 0.0, "grid_ok_prob": 0.0} for _ in range(12)]
    
    res = esh.calculate_forecast_esh(state, forecast, assume_island=True)
    assert res["critical_only_hours"] == pytest.approx(3.04)

def test_esh_lower_grid_ok_never_increases_esh() -> None:
    esh = ESHCalculator({"simulation_timestep_minutes": 5.0})
    state = DigitalTwinState(
        battery=BatteryState(soc=50.0),
        generator=GeneratorState(fuel_liters=0.0, is_available=False)
    )
    
    forecast_ok = [{"load_critical_kw": 10.0, "load_important_kw": 0.0, "load_flexible_kw": 0.0, "solar_kw": 0.0, "grid_ok_prob": 1.0} for _ in range(6)]
    forecast_ok += [{"load_critical_kw": 10.0, "load_important_kw": 0.0, "load_flexible_kw": 0.0, "solar_kw": 0.0, "grid_ok_prob": 0.0} for _ in range(6)]
    
    forecast_bad = [{"load_critical_kw": 10.0, "load_important_kw": 0.0, "load_flexible_kw": 0.0, "solar_kw": 0.0, "grid_ok_prob": 0.0} for _ in range(12)]
    
    res_ok = esh.calculate_forecast_esh(state, forecast_ok, assume_island=False)
    res_bad = esh.calculate_forecast_esh(state, forecast_bad, assume_island=False)
    
    assert res_bad["critical_only_hours"] < res_ok["critical_only_hours"]

def test_esh_shadow_twin_worst_case() -> None:
    esh = ESHCalculator({"simulation_timestep_minutes": 5.0})
    state = DigitalTwinState(
        battery=BatteryState(soc=50.0),
        generator=GeneratorState(fuel_liters=100.0, is_available=True)
    )
    
    forecast = [{"load_critical_kw": 10.0, "load_important_kw": 0.0, "load_flexible_kw": 0.0, "solar_kw": 0.0, "grid_ok_prob": 1.0} for _ in range(12)]
    
    res_expected = esh.calculate_forecast_esh(state, forecast, assume_island=False)
    assert res_expected["critical_only_hours"] == float("inf")
    
    res_shadow = esh.calculate_forecast_esh(state, forecast, assume_island=True)
    assert res_shadow["critical_only_hours"] < float("inf")
