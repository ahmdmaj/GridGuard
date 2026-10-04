import pytest
import math
from forecasting.service import ForecastService, WeatherCondition, DemandScenario

def get_mock_telemetry(timestamp="2026-01-01T12:00:00Z", solar_kw=10.0, load_kw=10.0) -> dict:
    return {
        "timestamp": timestamp,
        "solar_kw": solar_kw,
        "load_critical_kw": load_kw * 0.3,
        "load_important_kw": load_kw * 0.3,
        "load_flexible_kw": load_kw * 0.4,
    }

def test_forecast_produces_correct_number_of_steps():
    service = ForecastService()
    telemetry = get_mock_telemetry()
    forecasts = service.generate_forecast(telemetry, 24)
    assert len(forecasts) == 24

def test_forecast_output_keys_are_correct():
    service = ForecastService()
    telemetry = get_mock_telemetry()
    forecasts = service.generate_forecast(telemetry, 1)
    keys = list(forecasts[0].keys())
    assert set(keys) == {"solar_kw", "load_critical_kw", "load_important_kw", "load_flexible_kw"}

def test_solar_is_zero_at_night():
    service = ForecastService(weather_condition=WeatherCondition.CLEAR)
    telemetry = get_mock_telemetry(timestamp="2026-01-01T00:30:00Z", solar_kw=0.0)
    forecasts = service.generate_forecast(telemetry, 6) # 30 min ahead
    for f in forecasts:
        assert f["solar_kw"] == 0.0

def test_solar_is_zero_after_sunset():
    service = ForecastService()
    telemetry = get_mock_telemetry(timestamp="2026-01-01T19:00:00Z", solar_kw=0.0)
    forecasts = service.generate_forecast(telemetry, 6)
    for f in forecasts:
        assert f["solar_kw"] == 0.0

def test_solar_peaks_at_noon():
    service = ForecastService(solar_capacity_kw=10.0, weather_condition=WeatherCondition.CLEAR)
    # At 11:00, profile is ~9.659. Provide this as observed so correction factor is ~1.0
    telemetry = get_mock_telemetry(timestamp="2026-01-01T11:00:00Z", solar_kw=9.659)
    forecasts = service.generate_forecast(telemetry, 24) # 2 hours
    
    # At 12:00 (12 steps of 5 mins)
    solar_11 = forecasts[0]["solar_kw"]
    solar_12 = forecasts[11]["solar_kw"]
    solar_13 = forecasts[23]["solar_kw"]

    assert math.isclose(solar_12, 10.0, rel_tol=0.05)
    assert solar_11 < 10.0
    assert solar_13 < 10.0

def test_cloudy_condition_reduces_solar_by_factor():
    service_clear = ForecastService(weather_condition=WeatherCondition.CLEAR)
    service_cloudy = ForecastService(weather_condition=WeatherCondition.CLOUDY)
    service_rainy = ForecastService(weather_condition=WeatherCondition.RAINY)
    service_storm = ForecastService(weather_condition=WeatherCondition.STORM)
    
    # Pass matching observed solar to maintain a correction factor of ~1.0
    tel_clear = get_mock_telemetry(timestamp="2026-01-01T11:55:00Z", solar_kw=10.0)
    tel_cloudy = get_mock_telemetry(timestamp="2026-01-01T11:55:00Z", solar_kw=5.0)
    tel_rainy = get_mock_telemetry(timestamp="2026-01-01T11:55:00Z", solar_kw=1.5)
    tel_storm = get_mock_telemetry(timestamp="2026-01-01T11:55:00Z", solar_kw=0.5)
    
    forecasts_clear = service_clear.generate_forecast(tel_clear, 1)
    forecasts_cloudy = service_cloudy.generate_forecast(tel_cloudy, 1)
    forecasts_rainy = service_rainy.generate_forecast(tel_rainy, 1)
    forecasts_storm = service_storm.generate_forecast(tel_storm, 1)
    
    solar_clear = forecasts_clear[0]["solar_kw"]
    solar_cloudy = forecasts_cloudy[0]["solar_kw"]
    solar_rainy = forecasts_rainy[0]["solar_kw"]
    solar_storm = forecasts_storm[0]["solar_kw"]
    
    assert math.isclose(solar_cloudy, solar_clear * 0.50, rel_tol=0.01)
    assert math.isclose(solar_rainy, solar_clear * 0.15, rel_tol=0.01)
    assert math.isclose(solar_storm, solar_clear * 0.05, rel_tol=0.01)

def test_solar_rises_in_morning_forecast():
    service = ForecastService(weather_condition=WeatherCondition.CLEAR)
    telemetry = get_mock_telemetry(timestamp="2026-01-01T05:00:00Z", solar_kw=0.0)
    forecasts = service.generate_forecast(telemetry, 48) # 4 hours, to 09:00
    
    # Before sunrise (05:05)
    assert forecasts[0]["solar_kw"] == 0.0
    
    # 06:00 to 09:00 it should be rising
    solar_6 = forecasts[11]["solar_kw"] 
    solar_7 = forecasts[23]["solar_kw"]
    solar_8 = forecasts[35]["solar_kw"]
    
    assert solar_7 > solar_6
    assert solar_8 > solar_7

def test_load_is_lower_at_night_than_daytime():
    service = ForecastService()
    tel_night = get_mock_telemetry(timestamp="2026-01-01T03:00:00Z", load_kw=3.5)
    tel_day = get_mock_telemetry(timestamp="2026-01-01T16:00:00Z", load_kw=9.0)
    
    f_night = service.generate_forecast(tel_night, 1)
    f_day = service.generate_forecast(tel_day, 1)
    
    night_load = f_night[0]["load_critical_kw"] + f_night[0]["load_important_kw"] + f_night[0]["load_flexible_kw"]
    day_load = f_day[0]["load_critical_kw"] + f_day[0]["load_important_kw"] + f_day[0]["load_flexible_kw"]
    
    assert night_load < day_load

def test_high_demand_scenario_increases_load_forecast():
    service_normal = ForecastService(demand_scenario=DemandScenario.NORMAL)
    service_high = ForecastService(demand_scenario=DemandScenario.HIGH_DEMAND)
    
    telemetry = get_mock_telemetry(timestamp="2026-01-01T12:00:00Z", load_kw=9.0)
    
    f_normal = service_normal.generate_forecast(telemetry, 1)
    f_high = service_high.generate_forecast(telemetry, 1)
    
    load_normal = f_normal[0]["load_critical_kw"] + f_normal[0]["load_important_kw"] + f_normal[0]["load_flexible_kw"]
    load_high = f_high[0]["load_critical_kw"] + f_high[0]["load_important_kw"] + f_high[0]["load_flexible_kw"]
    
    assert load_high > load_normal
    assert math.isclose(load_high, load_normal * 1.30, rel_tol=0.01)

def test_forecast_values_are_non_negative():
    service = ForecastService(uncertainty_factor=0.5)
    telemetry = get_mock_telemetry()
    forecasts = service.generate_forecast(telemetry, 12)
    
    for f in forecasts:
        assert f["solar_kw"] >= 0.0
        assert f["load_critical_kw"] >= 0.0
        assert f["load_important_kw"] >= 0.0
        assert f["load_flexible_kw"] >= 0.0

def test_deterministic_with_zero_uncertainty():
    service = ForecastService(uncertainty_factor=0.0)
    telemetry = get_mock_telemetry()
    
    result_1 = service.generate_forecast(telemetry, 12)
    result_2 = service.generate_forecast(telemetry, 12)
    
    assert result_1 == result_2
