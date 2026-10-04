import pytest
import math
from digital_twin.state import DigitalTwinState, GridState, SolarState, BatteryState, GeneratorState, LoadState
from metrics.esh import ESHCalculator

def get_base_twin():
    return DigitalTwinState(
        timestamp="2026-01-01T12:00:00Z",
        grid=GridState(voltage_pu=0.0, is_available=False),
        solar=SolarState(power_kw=0.0),
        battery=BatteryState(soc=0.0),
        generator=GeneratorState(fuel_liters=0.0, is_available=False, power_kw=0.0),
        loads=LoadState(critical_kw=0.0, important_kw=0.0, flexible_kw=0.0)
    )

def get_base_config():
    return {
        "battery_capacity_kwh": 40.0,
        "battery_min_soc_percent": 20.0,
        "battery_max_soc_percent": 100.0,
        "battery_charge_efficiency": 1.0,
        "battery_discharge_efficiency": 1.0,
        "battery_max_discharge_kw": 20.0,
        "generator_capacity_kw": 15.0,
        "generator_fuel_rate_l_per_kwh": 0.3,
        "simulation_timestep_minutes": 5
    }

def get_dummy_forecast(solar=0.0, critical=0.0, important=0.0, flexible=0.0, steps=144):
    forecast = []
    for _ in range(steps):
        forecast.append({
            "solar_kw": solar,
            "load_critical_kw": critical,
            "load_important_kw": important,
            "load_flexible_kw": flexible,
            "grid_ok_prob": 0.0
        })
    return forecast

def test_esh_absolute_zero():
    twin = get_base_twin()
    twin.battery.soc = 0.0
    twin.solar.power_kw = 0.0
    twin.generator.is_available = False
    twin.loads.critical_kw = 10.0
    
    calc = ESHCalculator(get_base_config())
    forecast = get_dummy_forecast(critical=10.0)
    
    result = calc.calculate_forecast_esh(twin, forecast, assume_island=True)
    assert result["critical_only_hours"] == 0.0
    assert result["critical_and_important_hours"] == 0.0
    assert result["all_loads_hours"] == 0.0

def test_esh_phantom_fuel_rejection():
    twin = get_base_twin()
    twin.battery.soc = 0.0
    twin.solar.power_kw = 0.0
    twin.generator.fuel_liters = 500.0
    twin.generator.is_available = False
    twin.loads.critical_kw = 10.0
    
    calc = ESHCalculator(get_base_config())
    forecast = get_dummy_forecast(critical=10.0)
    
    result = calc.calculate_forecast_esh(twin, forecast, assume_island=True)
    assert result["critical_only_hours"] == 0.0

def test_esh_infinite_survival():
    twin = get_base_twin()
    twin.battery.soc = 50.0
    twin.generator.is_available = False
    twin.loads.critical_kw = 5.0
    twin.solar.power_kw = 5.0
    
    calc = ESHCalculator(get_base_config())
    forecast = get_dummy_forecast(solar=5.0, critical=5.0)
    
    result = calc.calculate_forecast_esh(twin, forecast, assume_island=True)
    assert math.isinf(result["critical_only_hours"])

def test_esh_exact_fractional_death():
    twin = get_base_twin()
    # Usable energy = 1.0 kWh. 
    # Formula: (soc - 20) / 100 * 40 = 1.0 => (soc - 20) = 2.5 => soc = 22.5
    twin.battery.soc = 22.5
    twin.generator.is_available = False
    twin.solar.power_kw = 0.0
    twin.loads.critical_kw = 6.0
    
    config = get_base_config()
    calc = ESHCalculator(config)
    forecast = get_dummy_forecast(critical=6.0)
    
    result = calc.calculate_forecast_esh(twin, forecast, assume_island=True)
    
    # 1.0 kWh / 6.0 kW = 0.1666... hours.
    expected_hours = 1.0 / 6.0
    assert abs(result["critical_only_hours"] - expected_hours) < 0.01

