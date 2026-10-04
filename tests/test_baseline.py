import pytest
from intelligence.baseline import BaselineHysteresisController

def test_baseline_grid_normal_charges_battery() -> None:
    controller = BaselineHysteresisController()
    
    # Needs charge
    telem = {"v_rms_pu": 1.0, "grid_connected": True, "soc": 50.0}
    command = controller.evaluate(1.0, 1.0, telem)
    assert command["gen_cmd"] == "STOP"
    assert command["shed_tier"] == 0
    assert command["inverter_mode"] == "GRID_PASS"
    
    # Floating
    telem = {"v_rms_pu": 1.0, "grid_connected": True, "soc": 100.0}
    command = controller.evaluate(1.0, 2.0, telem)
    assert command["gen_cmd"] == "STOP"
    assert command["inverter_mode"] == "GRID_PASS"

def test_baseline_island_generator_starts() -> None:
    controller = BaselineHysteresisController()
    telem = {"v_rms_pu": 0.0, "grid_connected": False, "soc": 25.0} # Low SOC, all connected
    command = controller.evaluate(1.0, 1.0, telem)
    
    assert command["gen_cmd"] == "START"
    assert command["inverter_mode"] == "ISLAND"

def test_baseline_soc_hysteresis() -> None:
    controller = BaselineHysteresisController()
    
    # Starts at 100%
    telem = {"v_rms_pu": 1.0, "grid_connected": True, "soc": 100.0}
    command = controller.evaluate(1.0, 1.0, telem)
    assert command["shed_tier"] == 0
    
    # Drops to 49.9 -> sheds flexible
    telem = {"v_rms_pu": 1.0, "grid_connected": True, "soc": 49.9}
    command = controller.evaluate(1.0, 2.0, telem)
    assert command["shed_tier"] == 1
    
    # Rises to 60.0 -> flexible stays shed (hysteresis)
    telem = {"v_rms_pu": 1.0, "grid_connected": True, "soc": 60.0}
    command = controller.evaluate(1.0, 3.0, telem)
    assert command["shed_tier"] == 1
    
    # Drops to 19.9 -> sheds important
    telem = {"v_rms_pu": 1.0, "grid_connected": True, "soc": 19.9}
    command = controller.evaluate(1.0, 4.0, telem)
    assert command["shed_tier"] == 2
    
    # Rises to 40.0 -> reconnects important, flexible still shed
    telem = {"v_rms_pu": 1.0, "grid_connected": True, "soc": 40.0}
    command = controller.evaluate(1.0, 5.0, telem)
    assert command["shed_tier"] == 1
    
    # Rises to 70.0 -> reconnects flexible
    telem = {"v_rms_pu": 1.0, "grid_connected": True, "soc": 70.0}
    command = controller.evaluate(1.0, 6.0, telem)
    assert command["shed_tier"] == 0
