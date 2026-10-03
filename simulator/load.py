from typing import Dict
from simulator.constants import LoadCategory

class BuildingLoad:
    def __init__(self) -> None:
        self.base_demand_kw: Dict[LoadCategory, float] = {
            LoadCategory.CRITICAL: 3.0,
            LoadCategory.IMPORTANT: 3.0,
            LoadCategory.FLEXIBLE: 4.0
        }
        self.current_demand_kw: Dict[LoadCategory, float] = self.base_demand_kw.copy()
        self.is_connected: Dict[LoadCategory, bool] = {
            LoadCategory.CRITICAL: True,
            LoadCategory.IMPORTANT: True,
            LoadCategory.FLEXIBLE: True
        }

    def set_demand_multiplier(self, multiplier: float) -> None:
        """Scales the current_demand_kw of all categories by multiplying base demand by multiplier."""
        for category, base_demand in self.base_demand_kw.items():
            self.current_demand_kw[category] = base_demand * multiplier

    def set_connection(self, category: LoadCategory, connected: bool) -> None:
        """Connects or disconnects a specific load category."""
        self.is_connected[category] = connected

    def get_demand_by_category(self, category: LoadCategory) -> float:
        """Returns demand if connected, else 0.0."""
        if self.is_connected[category]:
            return self.current_demand_kw[category]
        return 0.0

    def get_total_demand_kw(self) -> float:
        """Returns sum of demands for all connected categories."""
        total = 0.0
        for category in LoadCategory:
            if self.is_connected[category]:
                total += self.current_demand_kw[category]
        return total
