import math
from simulator.grid import Grid
from simulator.constants import GridState

def test_grid_initial_state():
    grid = Grid()
    assert grid.voltage == 230.0
    assert grid.state == GridState.NORMAL
    assert grid.is_available is True
    assert math.isinf(grid.get_power_capacity())

def test_grid_fail():
    grid = Grid()
    grid.fail()
    assert grid.voltage == 0.0
    assert grid.state == GridState.FAILED
    assert grid.is_available is False
    assert grid.get_power_capacity() == 0.0

def test_grid_degrade_mild():
    grid = Grid()
    grid.degrade(215.0)
    assert grid.voltage == 215.0
    assert grid.state == GridState.DEGRADED
    assert grid.is_available is True
    assert math.isinf(grid.get_power_capacity())

def test_grid_degrade_severe():
    grid = Grid()
    grid.degrade(190.0)
    assert grid.voltage == 190.0
    assert grid.state == GridState.FAILED
    assert grid.is_available is False
    assert grid.get_power_capacity() == 0.0

def test_grid_restore():
    grid = Grid()
    grid.fail()
    grid.restore()
    assert grid.voltage == 230.0
    assert grid.state == GridState.NORMAL
    assert grid.is_available is True
    assert math.isinf(grid.get_power_capacity())
