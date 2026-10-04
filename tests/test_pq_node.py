import pytest
import datetime
from physical.pq_node import PowerQualityNode

def test_pq_node_telemetry_generation() -> None:
    node = PowerQualityNode({})
    ts = datetime.datetime(2026, 1, 1, 12, 0)
    
    telem = node.generate_telemetry(ts, 0.95, True, "GRID_PASS", 2)
    assert telem is not None
    assert telem["schema_version"] == 1
    assert telem["seq"] == 1
    assert telem["v_rms_pu"] == 0.95
    assert telem["sts_state"] == "GRID_PASS"
    assert telem["transfer_count"] == 2
    
def test_pq_node_measurement_noise() -> None:
    node = PowerQualityNode({"measurement_noise_sigma_pu": 0.05, "seed": 42})
    ts = datetime.datetime(2026, 1, 1, 12, 0)
    
    telem = node.generate_telemetry(ts, 1.0, True, "GRID_PASS", 0)
    assert telem is not None
    assert telem["v_rms_pu"] != 1.0 # Should have noise added
    
def test_pq_node_dropout() -> None:
    node = PowerQualityNode({"dropout_prob": 1.0, "seed": 42})
    ts = datetime.datetime(2026, 1, 1, 12, 0)
    
    telem = node.generate_telemetry(ts, 1.0, True, "GRID_PASS", 0)
    assert telem is None # Should drop out
