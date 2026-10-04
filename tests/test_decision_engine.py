import pytest
from intelligence.decision_engine import DecisionEngine, EngineMode

def test_decision_engine_normal_to_support() -> None:
    engine = DecisionEngine({"t_support_enter_s": 10.0})
    
    # Grid drops to 0.93 (below 0.94)
    telem = {"v_rms_pu": 0.93, "grid_connected": True, "soc": 100.0}
    
    cmd = engine.evaluate(5.0, 5.0, telem, {}, {})
    assert engine.current_mode == EngineMode.NORMAL
    
    cmd = engine.evaluate(5.0, 10.0, telem, {}, {})
    assert engine.current_mode == EngineMode.SUPPORT
    assert cmd["inverter_mode"] == "SUPPORT"

def test_decision_engine_support_to_island() -> None:
    engine = DecisionEngine()
    engine.current_mode = EngineMode.SUPPORT
    
    # Grid drops to 0.84 (below 0.85) -> Instant island
    telem = {"v_rms_pu": 0.84, "grid_connected": True, "soc": 100.0}
    cmd = engine.evaluate(1.0, 1.0, telem, {}, {})
    assert engine.current_mode == EngineMode.ISLAND
    assert cmd["inverter_mode"] == "ISLAND"

def test_decision_engine_island_to_normal_dwell_and_soc() -> None:
    engine = DecisionEngine({"t_normal_return_s": 600.0, "reserve_floor_soc": 50.0})
    engine.current_mode = EngineMode.ISLAND
    
    # Grid recovers to 0.97
    telem = {"v_rms_pu": 0.97, "grid_connected": True, "soc": 40.0}
    
    # Wait 600s, but SOC is too low
    engine.evaluate(600.0, 600.0, telem, {}, {})
    assert engine.current_mode == EngineMode.ISLAND
    
    # SOC recovers
    telem["soc"] = 60.0
    engine.evaluate(1.0, 601.0, telem, {}, {})
    assert engine.current_mode == EngineMode.NORMAL

def test_decision_engine_transfer_limits() -> None:
    engine = DecisionEngine({"max_transfers_per_hour": 2, "min_dwell_s": 0.0, "t_normal_return_s": 0.0, "t_support_enter_s": 0.0})
    
    telem_island = {"v_rms_pu": 0.0, "grid_connected": False, "soc": 100.0}
    telem_normal = {"v_rms_pu": 1.0, "grid_connected": True, "soc": 100.0}
    
    # 1. Normal -> Island
    engine.evaluate(1.0, 1.0, telem_island, {}, {})
    assert engine.current_mode == EngineMode.ISLAND
    
    # 2. Island -> Normal
    engine.evaluate(1.0, 2.0, telem_normal, {}, {})
    assert engine.current_mode == EngineMode.NORMAL
    
    # 3. Normal -> Island (Allowed because going to a more protective mode doesn't get blocked)
    # Wait, if transfers hit the limit, it shouldn't block going to ISLAND! It should only block going to NORMAL.
    engine.evaluate(1.0, 3.0, telem_island, {}, {})
    assert engine.current_mode == EngineMode.ISLAND
    
    # 4. Island -> Normal (Blocked by transfer limit! 3 transfers already)
    engine.evaluate(1.0, 4.0, telem_normal, {}, {})
    assert engine.current_mode == EngineMode.ISLAND # Held in Island mode!

def test_decision_engine_load_shedding_staircase() -> None:
    engine = DecisionEngine()
    
    telem = {"v_rms_pu": 1.0, "grid_connected": True, "soc": 100.0}
    
    # Shed flexible
    esh_low = {"all_loads_hours": 3.0, "critical_and_important_hours": 3.0, "critical_only_hours": 10.0}
    cmd = engine.evaluate(1.0, 1.0, telem, esh_low, esh_low)
    assert cmd["shed_tier"] == 1
    
    # Still low
    esh_lower = {"all_loads_hours": 1.0, "critical_and_important_hours": 1.0, "critical_only_hours": 10.0}
    cmd = engine.evaluate(1.0, 2.0, telem, esh_lower, esh_lower)
    assert cmd["shed_tier"] == 2
    
    # Reconnect important
    esh_mid = {"all_loads_hours": 1.0, "critical_and_important_hours": 1.0, "critical_only_hours": 7.0}
    cmd = engine.evaluate(1.0, 3.0, telem, esh_mid, esh_mid)
    assert cmd["shed_tier"] == 1

def test_decision_engine_pre_peak_charging() -> None:
    engine = DecisionEngine({"pre_peak_start_h": 17.0, "pre_peak_end_h": 18.5, "pre_peak_soc_target": 90.0, "t_normal_return_s": 0.0, "min_dwell_s": 0.0})
    
    # 1. Not in peak window -> NORMAL
    telem_normal = {"ts": "2026-01-01T12:00:00Z", "v_rms_pu": 1.0, "grid_connected": True, "soc": 50.0}
    cmd1 = engine.evaluate(1.0, 1.0, telem_normal, {}, {})
    assert engine.current_mode == EngineMode.NORMAL
    assert cmd1["inverter_mode"] == "GRID_PASS"
    assert "charge_limit_kw" not in cmd1
    
    # 2. In peak window, SOC low -> SUPPORT
    telem_pre = {"ts": "2026-01-01T17:30:00Z", "v_rms_pu": 1.0, "grid_connected": True, "soc": 50.0}
    cmd2 = engine.evaluate(1.0, 2.0, telem_pre, {}, {})
    assert engine.current_mode == EngineMode.SUPPORT
    assert cmd2["inverter_mode"] == "SUPPORT"
    assert "charge_limit_kw" in cmd2
    
    # 3. In peak window, SOC high -> NORMAL
    telem_pre_high = {"ts": "2026-01-01T17:30:00Z", "v_rms_pu": 1.0, "grid_connected": True, "soc": 95.0}
    cmd3 = engine.evaluate(1.0, 3.0, telem_pre_high, {}, {})
    assert engine.current_mode == EngineMode.NORMAL
    assert cmd3["inverter_mode"] == "GRID_PASS"
