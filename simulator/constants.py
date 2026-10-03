from enum import Enum, auto

# Standard simulation timestep
SIMULATION_TIMESTEP_MINUTES = 5

class GridState(Enum):
    NORMAL = auto()
    DEGRADED = auto()
    FAILED = auto()

class OperatingMode(Enum):
    NORMAL = auto()
    GRID_STRESSED = auto()
    GRID_FAILED = auto()
    ENERGY_SCARCITY = auto()
    RECOVERY = auto()

class LoadCategory(Enum):
    CRITICAL = auto()
    IMPORTANT = auto()
    FLEXIBLE = auto()
