import pytest
from intelligence.esh import ESHCalculator

def test_esh_constant_load_no_solar() -> None:
    # 40 kWh battery, 20% min soc, 10kW load. 
    # Usable raw = 40 * 0.8 = 32 kWh.
    # Deliverable = 32 * 0.95 = 30.4 kWh.
    # Time = 30.4 / 10 = 3.04 hours.
    
    esh = ESHCalculator({"simulation_timestep_minutes": 5.0})
    state = {"soc": 100.0, "fuel_liters": 0.0, "gen_available": False}
    forecast = [{"load_critical_kw": 10.0, "solar_kw": 0.0, "grid_ok_prob": 0.0} for _ in range(12)] # 1 hour
    
    res = esh.calculate_forecast_esh(state, forecast, assume_island=True)
    assert res["critical_only_hours"] == pytest.approx(3.04)

def test_esh_lower_grid_ok_never_increases_esh() -> None:
    esh = ESHCalculator({"simulation_timestep_minutes": 5.0})
    state = {"soc": 50.0, "fuel_liters": 0.0, "gen_available": False}
    
    # Forecast 1: Grid OK for first 30 mins
    forecast_ok = [{"load_critical_kw": 10.0, "solar_kw": 0.0, "grid_ok_prob": 1.0} for _ in range(6)]
    forecast_ok += [{"load_critical_kw": 10.0, "solar_kw": 0.0, "grid_ok_prob": 0.0} for _ in range(6)]
    
    # Forecast 2: Grid Failed for all
    forecast_bad = [{"load_critical_kw": 10.0, "solar_kw": 0.0, "grid_ok_prob": 0.0} for _ in range(12)]
    
    res_ok = esh.calculate_forecast_esh(state, forecast_ok, assume_island=False)
    res_bad = esh.calculate_forecast_esh(state, forecast_bad, assume_island=False)
    
    assert res_bad["critical_only_hours"] < res_ok["critical_only_hours"]

def test_esh_shadow_twin_worst_case() -> None:
    esh = ESHCalculator({"simulation_timestep_minutes": 5.0})
    state = {"soc": 50.0, "fuel_liters": 100.0, "gen_available": True}
    
    # Forecast: Grid OK
    forecast = [{"load_critical_kw": 10.0, "solar_kw": 0.0, "grid_ok_prob": 1.0} for _ in range(12)]
    
    res_expected = esh.calculate_forecast_esh(state, forecast, assume_island=False)
    # Since grid is OK, expected survival is infinite
    assert res_expected["critical_only_hours"] == float("inf")
    
    # Shadow twin assumes grid is dead despite forecast
    res_shadow = esh.calculate_forecast_esh(state, forecast, assume_island=True)
    assert res_shadow["critical_only_hours"] < float("inf")
