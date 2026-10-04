from typing import List, Dict, Any
import numpy as np
import datetime

class SagEvent:
    def __init__(self, start_time: datetime.datetime, duration_s: float, depth_pu: float) -> None:
        self.start_time = start_time
        self.duration_s = duration_s
        self.depth_pu = depth_pu
        self.end_time = start_time + datetime.timedelta(seconds=duration_s)

    def is_active(self, current_time: datetime.datetime) -> bool:
        return self.start_time <= current_time < self.end_time

class FeederModel:
    def __init__(self, config: Dict[str, Any]) -> None:
        self.z_pu = config.get("z_pu", 0.05)
        self.p_feeder_rating_kw = config.get("p_feeder_rating_kw", 500.0)
        self.peak_start_hour = config.get("peak_start_hour", 18.5) # 18:30 CEB peak
        self.peak_end_hour = config.get("peak_end_hour", 22.5)   # 22:30 CEB peak
        self.bg_peak_kw = config.get("bg_peak_kw", 400.0)
        self.noise_sigma_pu = config.get("noise_sigma_pu", 0.005)
        self.seed = config.get("seed", 42)
        self.sag_events: List[SagEvent] = []
        
        self.rng = np.random.default_rng(self.seed)

    def add_sag_event(self, event: SagEvent) -> None:
        self.sag_events.append(event)

    def _get_background_load_kw(self, dt: datetime.datetime) -> float:
        # Simple smooth profile for background load
        hour = dt.hour + dt.minute / 60.0
        
        # Bell curve around the center of the peak window
        center_peak = (self.peak_start_hour + self.peak_end_hour) / 2.0
        width = (self.peak_end_hour - self.peak_start_hour) / 2.0
        
        # Base load is 30% of peak outside the peak window
        base_load = 0.3 * self.bg_peak_kw
        
        # Gaussian shape for the peak
        peak_shape = np.exp(-0.5 * ((hour - center_peak) / width)**2)
        
        return base_load + (self.bg_peak_kw - base_load) * peak_shape

    def get_voltage_pu(self, current_time: datetime.datetime, p_site_kw: float) -> float:
        v_source_pu = 1.0
        
        # 1. Background load
        p_bg_kw = self._get_background_load_kw(current_time)
        
        # 2. Voltage drop from impedance
        total_p_kw = p_bg_kw + p_site_kw
        v_drop_pu = self.z_pu * (total_p_kw / self.p_feeder_rating_kw)
        
        # 3. Sag events
        sag_pu = 0.0
        for event in self.sag_events:
            if event.is_active(current_time):
                sag_pu += event.depth_pu
                
        # 4. Noise
        noise_pu = self.rng.normal(0.0, self.noise_sigma_pu)
        
        v_pcc_pu = v_source_pu - v_drop_pu - sag_pu + noise_pu
        return max(0.0, v_pcc_pu)
