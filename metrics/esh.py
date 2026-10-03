from typing import Dict, Any, List
from simulator.constants import SIMULATION_TIMESTEP_MINUTES

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

    def calculate_forecast_esh(self, twin_state: Dict[str, Any], forecast: List[Dict[str, float]]) -> Dict[str, float]:
        # Step A: Calculate Available Energy (kWh)
        soc = twin_state["battery_state"]["soc"]
        usable_battery_soc = max(0.0, soc - self.battery_min_soc_percent)
        usable_battery_kwh = (usable_battery_soc / 100.0) * self.battery_capacity_kwh

        fuel_liters = twin_state["generator_state"]["fuel_liters"]
        usable_generator_kwh = fuel_liters / self.generator_fuel_consumption_rate

        total_available_kwh = usable_battery_kwh + usable_generator_kwh

        results = {}
        # Step B: Evaluate each of the three tiers
        for tier in ["critical_only", "critical_and_important", "all_loads"]:
            energy_remaining = total_available_kwh
            hours_survived = 0.0
            last_net_kw = 0.0

            # Step C: Forward Simulation Loop
            for step in forecast:
                if tier == "critical_only":
                    tier_demand = step["load_critical_kw"]
                elif tier == "critical_and_important":
                    tier_demand = step["load_critical_kw"] + step["load_important_kw"]
                else:  # all_loads
                    tier_demand = step["load_critical_kw"] + step["load_important_kw"] + step["load_flexible_kw"]

                net_kw = tier_demand - step["solar_kw"]
                last_net_kw = net_kw

                if net_kw > 0:
                    step_energy_kwh = net_kw * (SIMULATION_TIMESTEP_MINUTES / 60.0)
                    if energy_remaining >= step_energy_kwh:
                        energy_remaining -= step_energy_kwh
                        hours_survived += (SIMULATION_TIMESTEP_MINUTES / 60.0)
                    else:
                        fraction = energy_remaining / step_energy_kwh
                        hours_survived += fraction * (SIMULATION_TIMESTEP_MINUTES / 60.0)
                        energy_remaining = 0.0
                        break
                else:
                    hours_survived += (SIMULATION_TIMESTEP_MINUTES / 60.0)

            # Step D: Post-Forecast Extension
            if energy_remaining > 0 and len(forecast) > 0:
                if last_net_kw <= 0:
                    hours_survived += float('inf')
                else:
                    hours_survived += energy_remaining / last_net_kw

            results[f"{tier}_hours"] = hours_survived

        # Step E: Return the dictionary
        return results
