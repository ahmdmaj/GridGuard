from typing import Dict, Any, List
from simulator.constants import SIMULATION_TIMESTEP_MINUTES

_UNMET_TOLERANCE_KW = 0.001

class ESHCalculator:
    def __init__(self, config: dict = None) -> None:
        cfg = config or {}
        self.battery_capacity_kwh     = cfg.get("battery_capacity_kwh",      40.0)
        self.battery_min_soc_percent  = cfg.get("battery_min_soc_percent",   20.0)
        self.battery_max_soc_percent  = cfg.get("battery_max_soc_percent",  100.0)
        self.battery_max_charge_kw    = cfg.get("battery_max_charge_kw",     20.0)
        self.battery_max_discharge_kw = cfg.get("battery_max_discharge_kw",  20.0)
        self.battery_charge_eff       = cfg.get("battery_charge_efficiency",  0.95)
        self.battery_discharge_eff    = cfg.get("battery_discharge_efficiency", 0.95)
        self.generator_capacity_kw    = cfg.get("generator_capacity_kw",     15.0)
        self.generator_fuel_rate      = cfg.get("generator_fuel_rate_l_per_kwh", 0.3)
        self.timestep_minutes         = cfg.get("simulation_timestep_minutes", SIMULATION_TIMESTEP_MINUTES)

    def _usable_battery_raw_kwh(self, soc: float) -> float:
        return max(0.0, (soc - self.battery_min_soc_percent) / 100.0 * self.battery_capacity_kwh)

    @staticmethod
    def _tier_demand(tier: str, step: Dict[str, float]) -> float:
        if tier == "critical_only":
            return step.get("load_critical_kw", 0.0)
        if tier == "critical_and_important":
            return step.get("load_critical_kw", 0.0) + step.get("load_important_kw", 0.0)
        return step.get("load_critical_kw", 0.0) + step.get("load_important_kw", 0.0) + step.get("load_flexible_kw", 0.0)

    def calculate_forecast_esh(
        self,
        twin_state: Dict[str, Any],
        forecast: List[Dict[str, float]],
        assume_island: bool = False
    ) -> Dict[str, float]:
        """
        Calculates ESH.
        If assume_island is True, it ignores the grid_ok_prob in the forecast and assumes the grid is dead.
        Otherwise, it uses grid_ok_prob (1.0 = grid available, 0.0 = grid failed).
        """
        dt_hours = self.timestep_minutes / 60.0

        initial_bat_energy  = self._usable_battery_raw_kwh(twin_state.get("soc", 100.0)) # Note: Using direct telemetry instead of nested battery_state
        initial_fuel        = twin_state.get("fuel_liters", 100.0)
        initial_gen_avail   = twin_state.get("gen_available", True)

        results: Dict[str, float] = {}

        for tier in ("critical_only", "critical_and_important", "all_loads"):
            bat_energy = initial_bat_energy
            fuel       = initial_fuel
            gen_avail  = initial_gen_avail

            hours_survived   = 0.0
            failed           = False
            last_tier_demand = 0.0
            last_solar_kw    = 0.0
            last_grid_ok     = False

            for step in forecast:
                tier_demand_kw = self._tier_demand(tier, step)
                solar_kw       = step.get("solar_kw", 0.0)
                grid_ok_prob   = 0.0 if assume_island else step.get("grid_ok_prob", 0.0)
                grid_ok        = grid_ok_prob > 0.5 # Simple boolean logic for Phase 1
                
                last_tier_demand = tier_demand_kw
                last_solar_kw    = solar_kw
                last_grid_ok     = grid_ok

                if grid_ok:
                    # Grid satisfies all demand
                    remaining_kw = 0.0
                    # Grid charges battery
                    surplus_kw = self.battery_max_charge_kw # Effectively infinite grid power up to charge limit
                    charge_kw = min(surplus_kw, self.battery_max_charge_kw)
                    energy_in = charge_kw * dt_hours * self.battery_charge_eff
                    bat_room  = (self.battery_capacity_kwh * (self.battery_max_soc_percent - self.battery_min_soc_percent) / 100.0) - bat_energy
                    bat_energy += min(energy_in, max(0.0, bat_room))
                else:
                    # Island logic
                    remaining_kw = max(0.0, tier_demand_kw - solar_kw)
                    surplus_kw   = max(0.0, solar_kw - tier_demand_kw)

                    if surplus_kw > 0.0:
                        charge_kw = min(surplus_kw, self.battery_max_charge_kw)
                        energy_in = charge_kw * dt_hours * self.battery_charge_eff
                        bat_room  = (self.battery_capacity_kwh * (self.battery_max_soc_percent - self.battery_min_soc_percent) / 100.0) - bat_energy
                        bat_energy += min(energy_in, max(0.0, bat_room))

                    if remaining_kw > 0.0 and gen_avail and fuel > 0.0:
                        gen_kw      = min(remaining_kw, self.generator_capacity_kw)
                        fuel_needed = gen_kw * dt_hours * self.generator_fuel_rate
                        if fuel_needed > fuel:
                            gen_kw = (fuel / self.generator_fuel_rate) / dt_hours
                            fuel   = 0.0
                        else:
                            fuel -= fuel_needed
                        remaining_kw = max(0.0, remaining_kw - gen_kw)

                    if remaining_kw > 0.0 and bat_energy > 0.0:
                        energy_needed  = remaining_kw * dt_hours / self.battery_discharge_eff
                        max_bat_drain  = min(self.battery_max_discharge_kw * dt_hours, bat_energy)
                        actual_drain   = min(energy_needed, max_bat_drain)
                        bat_kw_out     = actual_drain * self.battery_discharge_eff / dt_hours
                        bat_energy    -= actual_drain
                        remaining_kw   = max(0.0, remaining_kw - bat_kw_out)

                if remaining_kw > _UNMET_TOLERANCE_KW:
                    supplied_kw    = tier_demand_kw - remaining_kw
                    fraction       = (supplied_kw / tier_demand_kw) if tier_demand_kw > 0 else 1.0
                    hours_survived += fraction * dt_hours
                    failed         = True
                    break

                hours_survived += dt_hours

            # Post-forecast extension
            if not failed and len(forecast) > 0:
                if last_grid_ok:
                    hours_survived = float("inf")
                else:
                    final_net_kw = last_tier_demand - last_solar_kw
                    if final_net_kw <= 0.0:
                        hours_survived = float("inf")
                    else:
                        bat_deliverable  = bat_energy * self.battery_discharge_eff
                        gen_energy_left  = (fuel / self.generator_fuel_rate if gen_avail and fuel > 0.0 else 0.0)
                        remaining_energy = bat_deliverable + gen_energy_left

                        gen_power   = self.generator_capacity_kw if (gen_avail and fuel > 0.0) else 0.0
                        max_rate_kw = self.battery_max_discharge_kw + gen_power

                        if final_net_kw > max_rate_kw:
                            if self.battery_max_discharge_kw > 0.0:
                                hours_survived += bat_deliverable / self.battery_max_discharge_kw
                        else:
                            hours_survived += remaining_energy / final_net_kw

            results[f"{tier}_hours"] = hours_survived

        return results
