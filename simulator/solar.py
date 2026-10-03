class SolarPV:
    def __init__(self, capacity_kw: float = 10.0) -> None:
        self.capacity_kw: float = capacity_kw
        self.availability_factor: float = 0.0
        self.current_output_kw: float = 0.0

    def set_availability(self, factor: float) -> None:
        """Sets the availability factor, clamping it between 0.0 and 1.0, and updates output."""
        self.availability_factor = max(0.0, min(1.0, factor))
        self.current_output_kw = self.capacity_kw * self.availability_factor

    def get_generation(self) -> float:
        """Returns the current output in kW."""
        return self.current_output_kw
