import datetime
import math
import random
from enum import Enum
from typing import List, Dict, Any

from simulator.constants import SIMULATION_TIMESTEP_MINUTES

class WeatherCondition(Enum):
    CLEAR = 1.00
    CLOUDY = 0.50
    RAINY = 0.15
    STORM = 0.05

class DemandScenario(Enum):
    NORMAL = 1.00
    HIGH_DEMAND = 1.30
    LOW_DEMAND = 0.70
    CRITICAL_EVENT = 0.50

class ForecastService:
    """
    Deterministic, profile-based forecast service for solar generation and load demand.
    
    Generates time-aware forecasts based on diurnal profiles, weather conditions,
    and demand scenarios. Uses the current telemetry timestamp and observed values 
    to anchor the profile to current reality, then projects forward.
    """
    def __init__(
        self,
        solar_capacity_kw: float = 10.0,
        peak_load_kw: float = 10.0,
        sunrise_hour: float = 6.0,
        sunset_hour: float = 18.0,
        weather_condition: WeatherCondition = WeatherCondition.CLEAR,
        demand_scenario: DemandScenario = DemandScenario.NORMAL,
        uncertainty_factor: float = 0.0,
        timestep_minutes: int = SIMULATION_TIMESTEP_MINUTES,
    ) -> None:
        self.solar_capacity_kw = solar_capacity_kw
        self.peak_load_kw = peak_load_kw
        self.sunrise_hour = sunrise_hour
        self.sunset_hour = sunset_hour
        self.weather_condition = weather_condition
        self.demand_scenario = demand_scenario
        self.uncertainty_factor = uncertainty_factor
        self.timestep_minutes = timestep_minutes

    def _get_solar_profile(self, hour_of_day: float) -> float:
        """Calculate the deterministic solar output given the hour of the day."""
        if hour_of_day < self.sunrise_hour or hour_of_day > self.sunset_hour:
            return 0.0
        
        # Sine curve mapping daylight hours
        t = (hour_of_day - self.sunrise_hour) / (self.sunset_hour - self.sunrise_hour)
        clear_sky_factor = math.sin(math.pi * t)
        
        return self.solar_capacity_kw * clear_sky_factor * self.weather_condition.value

    def _get_load_profile_fraction(self, hour_of_day: float) -> float:
        """Calculate the building load fraction (0.0 to 1.0) given the hour of the day."""
        # 4-zone diurnal model
        if 0.0 <= hour_of_day < 6.0:
            return 0.35  # Night base load
        elif 6.0 <= hour_of_day < 9.0:
            return 0.65  # Morning ramp
        elif 9.0 <= hour_of_day < 18.0:
            return 0.90  # Daytime operation
        else:
            return 0.70  # Evening ramp down

    def _apply_noise(self, base_value: float) -> float:
        """Apply random uniform noise if uncertainty_factor is > 0.0"""
        if self.uncertainty_factor <= 0.0:
            return max(0.0, base_value)
        
        noise = base_value * random.uniform(-self.uncertainty_factor, self.uncertainty_factor)
        return max(0.0, base_value + noise)

    def generate_forecast(self, current_telemetry: Dict[str, Any], steps_ahead: int = 12) -> List[Dict[str, float]]:
        # 1. Parse current time
        timestamp_str = current_telemetry.get("timestamp", "2026-01-01T00:00:00Z")
        if timestamp_str.endswith("Z"):
            timestamp_str = timestamp_str[:-1]
            
        try:
            current_dt = datetime.datetime.fromisoformat(timestamp_str)
        except ValueError:
            current_dt = datetime.datetime(2026, 1, 1, 0, 0, 0)
            
        dt = datetime.timedelta(minutes=self.timestep_minutes)
        current_hour = current_dt.hour + current_dt.minute / 60.0 + current_dt.second / 3600.0

        # 2. Solar Correction Factor
        observed_solar = current_telemetry.get("solar_kw", 0.0)
        profile_now_solar = self._get_solar_profile(current_hour)
        
        if profile_now_solar > 0.001:
            solar_correction = observed_solar / profile_now_solar
            solar_correction = max(0.2, min(2.0, solar_correction))
        else:
            solar_correction = 1.0

        # 3. Load Correction Factor
        observed_crit = current_telemetry.get("load_critical_kw", 0.0)
        observed_imp = current_telemetry.get("load_important_kw", 0.0)
        observed_flex = current_telemetry.get("load_flexible_kw", 0.0)
        observed_total_load = observed_crit + observed_imp + observed_flex

        if observed_total_load > 0.0:
            crit_frac = observed_crit / observed_total_load
            imp_frac = observed_imp / observed_total_load
            flex_frac = observed_flex / observed_total_load
        else:
            crit_frac = 1.0
            imp_frac = 0.0
            flex_frac = 0.0

        profile_now_load_frac = self._get_load_profile_fraction(current_hour)
        if profile_now_load_frac > 0.001 and self.peak_load_kw > 0:
            load_correction = observed_total_load / (self.peak_load_kw * profile_now_load_frac)
            load_correction = max(0.2, min(2.0, load_correction))
        else:
            load_correction = 1.0

        # 4. Generate forward steps
        forecasts = []
        for k in range(1, steps_ahead + 1):
            forecast_time = current_dt + k * dt
            hour_k = forecast_time.hour + forecast_time.minute / 60.0 + forecast_time.second / 3600.0

            # Solar forecast
            base_solar = self._get_solar_profile(hour_k) * solar_correction
            final_solar = self._apply_noise(base_solar)

            # Load forecast
            base_load_total = self.peak_load_kw * self._get_load_profile_fraction(hour_k) * self.demand_scenario.value * load_correction
            
            crit_kw = self._apply_noise(base_load_total * crit_frac)
            imp_kw = self._apply_noise(base_load_total * imp_frac)
            flex_kw = self._apply_noise(base_load_total * flex_frac)

            forecasts.append({
                "solar_kw": final_solar,
                "load_critical_kw": crit_kw,
                "load_important_kw": imp_kw,
                "load_flexible_kw": flex_kw,
            })

        return forecasts
