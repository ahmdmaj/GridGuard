from dataclasses import dataclass
from typing import Dict, Protocol, Optional
import datetime
import numpy as np

@dataclass
class ForecastBundle:
    t0: datetime.datetime
    step_s: int
    load_kw: Dict[str, np.ndarray]     # keys: "p10", "p50", "p90" (for total critical load, or tiered if needed)
    solar_kw: Dict[str, np.ndarray]    # keys: "p10", "p50", "p90"
    grid_ok_prob: np.ndarray           # probability grid is usable (1.0 = fine, 0.0 = outage/sag)
    confidence: float                  # 0..1
    source: str                        # "ml" or "rule"

class ForecastService(Protocol):
    def forecast(self, telemetry_history: list, now: datetime.datetime, horizon_s: int) -> ForecastBundle:
        ...
