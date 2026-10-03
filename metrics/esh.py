from typing import Dict, Any

class ESHCalculator:
    def __init__(self) -> None:
        self.battery_capacity_kwh: float = 40.0
        self.battery_min_soc_percent: float = 20.0
        self.generator_fuel_consumption_rate: float = 0.3  # liters per kWh

    def calculate_instantaneous_esh(self, twin_state: Dict[str, Any]) -> Dict[str, float]:
        # Step A: Calculate Available Energy (kWh)
        soc = twin_state["battery_state"]["soc"]
        usable_battery_soc = max(0.0, soc - self.battery_min_soc_percent)
        usable_battery_kwh = (usable_battery_soc / 100.0) * self.battery_capacity_kwh

        fuel_liters = twin_state["generator_state"]["fuel_liters"]
        usable_generator_kwh = fuel_liters / self.generator_fuel_consumption_rate

        total_available_kwh = usable_battery_kwh + usable_generator_kwh

        # Step B: Define Load Tiers
        crit = twin_state["load_state"]["critical_kw"]
        imp = twin_state["load_state"]["important_kw"]
        flex = twin_state["load_state"]["flexible_kw"]

        tiers = {
            "critical_only": crit,
            "critical_and_important": crit + imp,
            "all_loads": crit + imp + flex
        }

        # Step C & D: Calculate Horizon per Tier
        solar_gen = twin_state["solar_state"]["generation_kw"]
        results = {}
        for tier_name, tier_load in tiers.items():
            net_demand = tier_load - solar_gen
            if net_demand <= 0:
                results[f"{tier_name}_hours"] = float('inf')
            else:
                results[f"{tier_name}_hours"] = total_available_kwh / net_demand

        return results
