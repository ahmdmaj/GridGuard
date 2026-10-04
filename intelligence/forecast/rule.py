import datetime
import numpy as np
from intelligence.forecast.base import ForecastBundle, ForecastService

class RuleForecastService(ForecastService):
    def __init__(self):
        pass
        
    def forecast(self, telemetry_history: list, now: datetime.datetime, horizon_s: int) -> ForecastBundle:
        step_s = 300
        steps = int(horizon_s / step_s)
        
        load_p50 = np.full(steps, 4.0) # Assumes 4.0 kW critical load
        solar_p50 = np.zeros(steps)
        grid_ok_prob = np.ones(steps)
        
        # Simple rule: if inside peak window, grid ok prob is 1.0 UNLESS recent voltage was bad
        # Since this is a simple mock rule without seeing the whole history easily, we just output 1.0.
        
        # Time-based solar rule
        for i in range(steps):
            t = now + datetime.timedelta(seconds=i*step_s)
            if 8 <= t.hour <= 16:
                solar_p50[i] = 10.0 # Arbitrary rule
                
        return ForecastBundle(
            t0=now,
            step_s=step_s,
            load_kw={"p10": load_p50 * 0.9, "p50": load_p50, "p90": load_p50 * 1.1},
            solar_kw={"p10": solar_p50 * 0.5, "p50": solar_p50, "p90": solar_p50 * 1.2},
            grid_ok_prob=grid_ok_prob,
            confidence=1.0,
            source="rule"
        )
