import pytest
from physical.inverter_sts import InverterSTS, InverterMode

def test_inverter_grid_pass() -> None:
    inv = InverterSTS({})
    # Voltage should just pass through
    v_pu, dropout, overload = inv.step(InverterMode.GRID_PASS, 1.0, pcc_v_pu=0.92, load_kw=5.0)
    assert v_pu == pytest.approx(0.92)
    assert dropout == 0.0
    assert overload is False

def test_inverter_support_mode_regulates_voltage() -> None:
    inv = InverterSTS({"inverter_rating_kw": 20.0})
    # Force state
    inv.current_mode = InverterMode.SUPPORT
    inv.time_in_mode_s = 10.0
    
    # Grid is sagging, but inverter supports it
    v_pu, dropout, overload = inv.step(InverterMode.SUPPORT, 1.0, pcc_v_pu=0.85, load_kw=15.0)
    assert v_pu == pytest.approx(1.0)
    assert dropout == 0.0
    assert overload is False

def test_inverter_overload_collapses_voltage() -> None:
    inv = InverterSTS({"inverter_rating_kw": 10.0})
    inv.current_mode = InverterMode.ISLAND
    inv.time_in_mode_s = 10.0
    
    # Load exceeds rating (15 > 10)
    v_pu, dropout, overload = inv.step(InverterMode.ISLAND, 1.0, pcc_v_pu=0.0, load_kw=15.0)
    assert overload is True
    assert v_pu < 1.0
    assert v_pu == pytest.approx(10.0 / 15.0)

def test_inverter_transfer_incurs_dropout_and_dwell() -> None:
    inv = InverterSTS({"transfer_time_ms": 15.0, "min_dwell_s": 5.0})
    
    # Initially GRID_PASS. Request SUPPORT. Should transfer and incur dropout.
    v_pu, dropout, overload = inv.step(InverterMode.SUPPORT, 1.0, pcc_v_pu=0.9, load_kw=5.0)
    assert inv.current_mode == InverterMode.SUPPORT
    assert dropout == 15.0
    
    # Immediately request ISLAND. Should NOT transfer yet due to min_dwell_s (1.0 < 5.0).
    v_pu2, dropout2, overload2 = inv.step(InverterMode.ISLAND, 1.0, pcc_v_pu=0.0, load_kw=5.0)
    assert inv.current_mode == InverterMode.SUPPORT
    assert dropout2 == 0.0
    
    # Step 5 seconds, request ISLAND again. Should transfer now.
    inv.step(InverterMode.ISLAND, 5.0, pcc_v_pu=0.0, load_kw=5.0)
    v_pu3, dropout3, overload3 = inv.step(InverterMode.ISLAND, 1.0, pcc_v_pu=0.0, load_kw=5.0)
    assert inv.current_mode == InverterMode.ISLAND
    assert dropout3 == 15.0
