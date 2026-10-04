from typing import Dict, Any, Optional
import datetime
import numpy as np

class PowerQualityNode:
    def __init__(self, config: Dict[str, Any]) -> None:
        self.noise_sigma_pu = config.get("measurement_noise_sigma_pu", 0.0)
        self.dropout_prob = config.get("dropout_prob", 0.0)
        self.seq = 0
        self.rng = np.random.default_rng(config.get("seed", 42))

    def generate_telemetry(self, ts: datetime.datetime, v_pcc_pu: float, grid_connected: bool, sts_state: str, transfer_count: int) -> Optional[Dict[str, Any]]:
        # Handle dropout
        if self.dropout_prob > 0 and self.rng.random() < self.dropout_prob:
            return None
            
        # Add measurement noise
        measured_v = v_pcc_pu
        if self.noise_sigma_pu > 0:
            measured_v += self.rng.normal(0.0, self.noise_sigma_pu)
            
        self.seq += 1
        
        return {
            "schema_version": 1,
            "ts": ts.isoformat() + "Z",
            "seq": self.seq,
            "v_rms_pu": measured_v,
            "freq_hz": 50.0 if grid_connected else 0.0, # Simple freq for now
            "grid_connected": grid_connected,
            "sts_state": sts_state,
            "transfer_count": transfer_count
        }
