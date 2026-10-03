import pytest
from forecasting.service import ForecastService
from simulator.telemetry import TelemetrySnapshot

def get_mock_telemetry() -> TelemetrySnapshot:
    return {
        "timestamp": "T1",
        "grid_available": True,
        "grid_voltage": 220.0,
        "solar_kw": 5.0,
        "battery_soc": 100.0,
        "battery_kw": 0.0,
        "generator_kw": 0.0,
        "generator_fuel_liters": 100.0,
        "generator_available": True,
        "load_critical_kw": 3.0,
        "load_important_kw": 3.0,
        "load_flexible_kw": 4.0,
        "unserved_kw": 0.0
    }

def test_forecasting_zero_noise() -> None:
    service = ForecastService(uncertainty_factor=0.0)
    mock_telemetry = get_mock_telemetry()
    
    forecasts = service.generate_forecast(mock_telemetry, steps_ahead=3)
    
    assert len(forecasts) == 3
    for forecast in forecasts:
        assert forecast["solar_kw"] == 5.0
        assert forecast["load_critical_kw"] == 3.0
        assert forecast["load_important_kw"] == 3.0
        assert forecast["load_flexible_kw"] == 4.0

def test_forecasting_noise_application() -> None:
    service = ForecastService(uncertainty_factor=0.20)
    mock_telemetry = get_mock_telemetry()
    mock_telemetry["solar_kw"] = 10.0
    
    forecasts = service.generate_forecast(mock_telemetry, steps_ahead=10)
    
    for forecast in forecasts:
        # With 20% uncertainty, solar_kw should be between 8.0 and 12.0
        assert 8.0 <= forecast["solar_kw"] <= 12.0

def test_forecasting_negative_clamping() -> None:
    service = ForecastService(uncertainty_factor=0.50)
    mock_telemetry = get_mock_telemetry()
    mock_telemetry["solar_kw"] = 0.0
    mock_telemetry["load_critical_kw"] = 0.0
    
    forecasts = service.generate_forecast(mock_telemetry, steps_ahead=5)
    
    for forecast in forecasts:
        assert forecast["solar_kw"] == 0.0
        assert forecast["load_critical_kw"] == 0.0
