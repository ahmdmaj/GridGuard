import pytest
from intelligence.baseline import BaselineController

def test_baseline_grid_normal_charges_battery() -> None:
    controller = BaselineController()
    
    # Needs charge
    telem = {"v_rms_pu": 1.0, "grid_connected": True, "soc": 50.0}
    command = controller.evaluate(1.0, 1.0, telem)
    assert command["gen_cmd"] == "STOP"
    assert command["shed_tier"] == 0
    assert command["inverter_mode"] == "GRID_PASS"

def test_baseline_battery_command_accounts_for_generator() -> None:
    controller = BaselineController()
    telem = {"v_rms_pu": 0.0, "grid_connected": False, "soc": 80.0}
    command = controller.evaluate(1.0, 1.0, telem)
    assert command["inverter_mode"] == "ISLAND"

def test_baseline_soc_hysteresis() -> None:
    controller = BaselineController()
    
    # Starts at 100%
    telem = {"v_rms_pu": 1.0, "grid_connected": True, "soc": 100.0}
    command = controller.evaluate(1.0, 1.0, telem)
    assert command["shed_tier"] == 0
    
    # Drops to 49.9 -> sheds flexible
    telem = {"v_rms_pu": 1.0, "grid_connected": True, "soc": 49.9}
    command = controller.evaluate(1.0, 2.0, telem)
    assert command["shed_tier"] == 1
    
    # Drops to 19.9 -> sheds important
    telem = {"v_rms_pu": 1.0, "grid_connected": True, "soc": 19.9}
    command = controller.evaluate(1.0, 4.0, telem)
    assert command["shed_tier"] == 2
