from typing import List, Dict, Any
from simulator.telemetry import TelemetrySnapshot

class MetricsCollector:
    def calculate_metrics(self, history: List[TelemetrySnapshot]) -> Dict[str, float]:
        if not history:
            return {
                "critical_energy_served_kwh": 0.0,
                "total_unserved_energy_kwh": 0.0,
                "generator_runtime_hours": 0.0,
                "fuel_consumed_liters": 0.0,
                "solar_energy_used_kwh": 0.0
            }

        critical_energy_served_kwh = 0.0
        total_unserved_energy_kwh = 0.0
        generator_runtime_hours = 0.0
        solar_energy_used_kwh = 0.0
        time_factor = 5.0 / 60.0

        for step in history:
            critical_energy_served_kwh += step["load_critical_kw"] * time_factor
            total_unserved_energy_kwh += step["unserved_kw"] * time_factor
            if step["generator_kw"] > 0.0:
                generator_runtime_hours += time_factor
            solar_energy_used_kwh += step["solar_kw"] * time_factor

        fuel_consumed_liters = history[0]["generator_fuel_liters"] - history[-1]["generator_fuel_liters"]

        return {
            "critical_energy_served_kwh": critical_energy_served_kwh,
            "total_unserved_energy_kwh": total_unserved_energy_kwh,
            "generator_runtime_hours": generator_runtime_hours,
            "fuel_consumed_liters": fuel_consumed_liters,
            "solar_energy_used_kwh": solar_energy_used_kwh
        }
