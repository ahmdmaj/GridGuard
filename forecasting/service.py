import random
from typing import List, Dict
from simulator.telemetry import TelemetrySnapshot

class ForecastService:
    def __init__(self, uncertainty_factor: float = 0.10) -> None:
        self.uncertainty_factor = uncertainty_factor

    def _apply_noise(self, base_value: float) -> float:
        noise = base_value * random.uniform(-self.uncertainty_factor, self.uncertainty_factor)
        return max(0.0, base_value + noise)

    def generate_forecast(self, current_telemetry: TelemetrySnapshot, steps_ahead: int) -> List[Dict[str, float]]:
        forecasts = []
        for _ in range(steps_ahead):
            forecast = {
                "solar_kw": self._apply_noise(current_telemetry["solar_kw"]),
                "load_critical_kw": self._apply_noise(current_telemetry["load_critical_kw"]),
                "load_important_kw": self._apply_noise(current_telemetry["load_important_kw"]),
                "load_flexible_kw": self._apply_noise(current_telemetry["load_flexible_kw"]),
            }
            forecasts.append(forecast)
        return forecasts
