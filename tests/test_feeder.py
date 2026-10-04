import pytest
import datetime
from physical.feeder import FeederModel, SagEvent

def test_feeder_background_load_reduces_voltage() -> None:
    config = {"z_pu": 0.1, "p_feeder_rating_kw": 500.0, "bg_peak_kw": 400.0, "noise_sigma_pu": 0.0}
    feeder = FeederModel(config)
    
    dt_off_peak = datetime.datetime(2026, 1, 1, 12, 0) # Noon
    dt_peak = datetime.datetime(2026, 1, 1, 20, 30)    # 20:30 (Center of peak)
    
    v_off_peak = feeder.get_voltage_pu(dt_off_peak, p_site_kw=0.0)
    v_peak = feeder.get_voltage_pu(dt_peak, p_site_kw=0.0)
    
    assert v_peak < v_off_peak
    # Expected off peak: base load ~ 120kW -> drop = 0.1 * (120/500) = 0.024 -> V ~ 0.976
    # Expected peak: 400kW -> drop = 0.1 * (400/500) = 0.08 -> V ~ 0.92
    assert v_peak < 0.94 # Peak load alone drops voltage below 0.94 in this config

def test_feeder_site_load_reduces_voltage_further() -> None:
    config = {"z_pu": 0.1, "p_feeder_rating_kw": 500.0, "bg_peak_kw": 200.0, "noise_sigma_pu": 0.0}
    feeder = FeederModel(config)
    dt = datetime.datetime(2026, 1, 1, 12, 0)
    
    v_no_site = feeder.get_voltage_pu(dt, p_site_kw=0.0)
    v_with_site = feeder.get_voltage_pu(dt, p_site_kw=100.0)
    
    assert v_with_site < v_no_site
    # The drop should be exactly z_pu * (100 / 500) = 0.1 * 0.2 = 0.02
    assert v_with_site == pytest.approx(v_no_site - 0.02)

def test_feeder_determinism() -> None:
    config = {"noise_sigma_pu": 0.05, "seed": 42}
    
    feeder1 = FeederModel(config)
    feeder2 = FeederModel(config)
    
    dt = datetime.datetime(2026, 1, 1, 12, 0)
    
    v1 = [feeder1.get_voltage_pu(dt, 0.0) for _ in range(5)]
    v2 = [feeder2.get_voltage_pu(dt, 0.0) for _ in range(5)]
    
    assert v1 == v2

def test_feeder_sag_event() -> None:
    config = {"noise_sigma_pu": 0.0}
    feeder = FeederModel(config)
    
    dt_start = datetime.datetime(2026, 1, 1, 12, 0)
    dt_during = dt_start + datetime.timedelta(seconds=10)
    dt_after = dt_start + datetime.timedelta(seconds=20)
    
    feeder.add_sag_event(SagEvent(start_time=dt_start, duration_s=15.0, depth_pu=0.15))
    
    v_before = feeder.get_voltage_pu(dt_start - datetime.timedelta(seconds=1), 0.0)
    v_during = feeder.get_voltage_pu(dt_during, 0.0)
    v_after = feeder.get_voltage_pu(dt_after, 0.0)
    
    assert v_during == pytest.approx(v_before - 0.15)
    assert v_after == pytest.approx(v_before, abs=1e-5)
