from simulator.constants import GridState

class Grid:
    def __init__(self) -> None:
        self.voltage: float = 230.0
        self.state: GridState = GridState.NORMAL
        self.is_available: bool = True

    def fail(self) -> None:
        """Simulates a complete blackout."""
        self.voltage = 0.0
        self.state = GridState.FAILED
        self.is_available = False

    def degrade(self, voltage: float) -> None:
        """Simulates a brownout/sag."""
        self.voltage = voltage
        if self.voltage < 200.0:
            self.state = GridState.FAILED
            self.is_available = False
        else:
            self.state = GridState.DEGRADED
            self.is_available = True

    def restore(self) -> None:
        """Returns to 230V and NORMAL state."""
        self.voltage = 230.0
        self.state = GridState.NORMAL
        self.is_available = True

    def get_power_capacity(self) -> float:
        """Returns infinite capacity if available, otherwise 0."""
        if self.is_available:
            return float('inf')
        return 0.0
