import pytest
import math
from metrics.collector import MetricsCollector
from simulator.telemetry import TelemetrySnapshot

def test_metrics_calculation() -> None:
    collector = MetricsCollector()
    
    history: list[TelemetrySnapshot] = [
        {
            "timestamp": "T1", "grid_available": False, "grid_voltage": 0.0,
            "solar_kw": 2.0, "battery_soc": 50.0, "battery_kw": 0.0,
            "generator_kw": 15.0, "generator_fuel_liters": 100.0,
            "load_critical_kw": 3.0, "load_important_kw": 0.0, "load_flexible_kw": 0.0, "unserved_kw": 0.0
        },
        {
            "timestamp": "T2", "grid_available": False, "grid_voltage": 0.0,
            "solar_kw": 2.0, "battery_soc": 50.0, "battery_kw": 0.0,
            "generator_kw": 15.0, "generator_fuel_liters": 99.0,
            "load_critical_kw": 3.0, "load_important_kw": 0.0, "load_flexible_kw": 0.0, "unserved_kw": 1.0
        },
        {
            "timestamp": "T3", "grid_available": False, "grid_voltage": 0.0,
            "solar_kw": 2.0, "battery_soc": 50.0, "battery_kw": 0.0,
            "generator_kw": 0.0, "generator_fuel_liters": 98.0,
            "load_critical_kw": 3.0, "load_important_kw": 0.0, "load_flexible_kw": 0.0, "unserved_kw": 0.0
        }
    ]
    
    metrics = collector.calculate_metrics(history)
    
    assert math.isclose(metrics["critical_energy_served_kwh"], 9.0 * (5.0/60.0))
    assert math.isclose(metrics["total_unserved_energy_kwh"], 1.0 * (5.0/60.0))
    assert math.isclose(metrics["generator_runtime_hours"], 10.0 / 60.0)
    assert math.isclose(metrics["fuel_consumed_liters"], 2.0)
    assert math.isclose(metrics["solar_energy_used_kwh"], 6.0 * (5.0/60.0))
