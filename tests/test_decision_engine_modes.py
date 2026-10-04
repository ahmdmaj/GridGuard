import pytest
from intelligence.decision_engine import DecisionEngine

def test_engine_defers_generator_if_solar_incoming():
    engine = DecisionEngine()
    telem = {"v_rms_pu": 0.0, "grid_connected": False, "soc": 25.0}
    full_esh = {"critical_only_hours": 10.0}
    shadow_esh = {"critical_only_hours": 10.0} # > 2.0
    cmd = engine.evaluate(1.0, 1.0, telem, full_esh, shadow_esh)
    assert cmd["gen_cmd"] == "STOP"
    
def test_engine_starts_generator_if_forecast_poor():
    engine = DecisionEngine()
    telem = {"v_rms_pu": 0.0, "grid_connected": False, "soc": 40.0}
    full_esh = {"critical_only_hours": 1.5}
    shadow_esh = {"critical_only_hours": 1.5} # < 2.0
    cmd = engine.evaluate(1.0, 1.0, telem, full_esh, shadow_esh)
    assert cmd["gen_cmd"] == "START"
    
def test_engine_hard_soc_safety_net():
    engine = DecisionEngine()
    telem = {"v_rms_pu": 0.0, "grid_connected": False, "soc": 19.0}
    full_esh = {"critical_only_hours": 10.0}
    shadow_esh = {"critical_only_hours": 10.0} # miraculously high
    cmd = engine.evaluate(1.0, 1.0, telem, full_esh, shadow_esh)
    assert cmd["gen_cmd"] == "START"
