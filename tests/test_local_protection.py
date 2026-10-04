import pytest
from physical.local_protection import LocalProtection
from physical.inverter_sts import InverterMode

def test_local_protection_healthy_comms() -> None:
    lp = LocalProtection({"watchdog_s": 30.0})
    lp.receive_command()
    
    # Step 10 seconds, comms are healthy (10 < 30)
    cmd = lp.step(10.0, 0.9, InverterMode.GRID_PASS)
    assert cmd is None # No fallback

def test_local_protection_comms_loss_island() -> None:
    lp = LocalProtection({"watchdog_s": 30.0})
    
    # Step 35 seconds, no comms. V < 0.8 -> ISLAND
    cmd = lp.step(35.0, 0.75, InverterMode.GRID_PASS)
    assert cmd == InverterMode.ISLAND

def test_local_protection_comms_loss_support_delay() -> None:
    lp = LocalProtection({"watchdog_s": 30.0})
    
    # Step 31 seconds, no comms. V = 1.0 (Healthy)
    lp.step(31.0, 1.0, InverterMode.GRID_PASS)
    
    # Step 4 seconds, V = 0.90
    cmd1 = lp.step(4.0, 0.90, InverterMode.GRID_PASS)
    assert cmd1 == InverterMode.GRID_PASS # Takes 5s of <0.92 to trigger SUPPORT
    
    # Step 5 more seconds
    cmd2 = lp.step(5.0, 0.90, InverterMode.GRID_PASS)
    assert cmd2 == InverterMode.SUPPORT
    
def test_local_protection_return_to_grid_pass_delay() -> None:
    lp = LocalProtection({"watchdog_s": 30.0})
    
    # Trigger SUPPORT
    lp.step(35.0, 0.90, InverterMode.GRID_PASS) # 35s total, 35s < 0.92 (Wait, step adds 35s to timer!)
    # Actually, the first step that exceeds watchdog starts tracking. Let's do it cleanly.
    
    lp.receive_command()
    lp.step(35.0, 1.0, InverterMode.SUPPORT) # Timeout reached, fallback starts at SUPPORT
    
    # V >= 0.96 for 500 seconds (not enough)
    cmd1 = lp.step(500.0, 1.0, InverterMode.SUPPORT)
    assert cmd1 == InverterMode.SUPPORT
    
    # Another 100 seconds (total 600)
    cmd2 = lp.step(100.0, 1.0, InverterMode.SUPPORT)
    assert cmd2 == InverterMode.GRID_PASS

def test_local_protection_recovery() -> None:
    lp = LocalProtection({"watchdog_s": 30.0})
    
    # Comms lost
    cmd1 = lp.step(35.0, 0.7, InverterMode.GRID_PASS)
    assert cmd1 == InverterMode.ISLAND
    
    # Comms restored
    lp.receive_command()
    cmd2 = lp.step(1.0, 0.7, InverterMode.ISLAND)
    assert cmd2 is None # Control returned to master
