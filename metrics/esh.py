from typing import Dict, Any, List
from simulator.constants import SIMULATION_TIMESTEP_MINUTES

# Minimum unmet demand (kW) before a timestep is declared a failure.
# Prevents false failures from floating-point rounding at boundaries.
_UNMET_TOLERANCE_KW = 0.001


class ESHCalculator:
    """
    Energy Survival Horizon (ESH) Calculator.

    Estimates how long the building energy system can continuously supply each
    load tier before the critical load can no longer be met.

    Two methods are provided:

    calculate_instantaneous_esh:
        Fast formula-based estimate intended for real-time dashboard display.
        Assumes current solar and load conditions remain constant indefinitely.
        When demand exceeds the system's maximum instantaneous power output,
        returns 0.0 — this is the "time-to-power-failure = immediate" case.

    calculate_forecast_esh:
        Authoritative forward-simulation used by the Decision Engine.
        Steps through the forecast one timestep at a time, tracking battery
        energy and generator fuel as they evolve.

    GENERATOR POLICY (both methods):
        The generator is modelled as running throughout the horizon if it is
        available (is_available=True) and has fuel (fuel_liters > 0).
        This is the OPTIMISTIC (upper-bound) policy: ESH is the best-case
        survival estimate. The Decision Engine adds conservatism on top.

    DISPATCH ORDER (forecast method, optimistic policy):
        Solar -> Generator -> Battery
        Surplus solar charges the battery within its power and capacity limits.

    CONFIGURATION:
        All physical parameters are supplied via a config dict at construction.
        Defaults match the simulator's Battery and Generator components.
        Long-term these should be loaded from a shared system configuration
        rather than maintained in two places.
    """

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

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------

    def _usable_battery_raw_kwh(self, soc: float) -> float:
        """
        Raw energy stored above the minimum SOC threshold (kWh).

        This is the energy held in storage. Actual energy deliverable to loads
        is lower by the discharge efficiency factor and is computed at the
        point of use.
        """
        return max(0.0, (soc - self.battery_min_soc_percent) / 100.0 * self.battery_capacity_kwh)

    @staticmethod
    def _tier_demand(tier: str, step: Dict[str, float]) -> float:
        """Return total demand (kW) for the given load tier from a forecast step."""
        if tier == "critical_only":
            return step["load_critical_kw"]
        if tier == "critical_and_important":
            return step["load_critical_kw"] + step["load_important_kw"]
        return step["load_critical_kw"] + step["load_important_kw"] + step["load_flexible_kw"]

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def calculate_instantaneous_esh(self, twin_state: Dict[str, Any]) -> Dict[str, float]:
        """
        Fast formula-based ESH snapshot.

        Assumes current solar and load remain constant. Uses the energy-duration
        formula (total_energy / net_demand_rate) when the power constraint is
        satisfied, i.e. net_demand_kw <= battery_max_discharge + generator_capacity.

        When demand EXCEEDS the system's maximum power output, the formula is
        not valid. In this case ESH = 0.0 is returned, indicating that power
        failure is already occurring (time-to-power-failure = immediate).

        Returns:
            Dict with keys:
                "critical_only_hours"
                "critical_and_important_hours"
                "all_loads_hours"
        """
        soc = twin_state["battery_state"]["soc"]
        usable_bat_raw_kwh = self._usable_battery_raw_kwh(soc)
        # Deliverable energy to loads (discharge efficiency applied)
        usable_bat_kwh = usable_bat_raw_kwh * self.battery_discharge_eff

        gen_available = twin_state["generator_state"].get("is_available", True)
        fuel_liters   = twin_state["generator_state"]["fuel_liters"]
        if gen_available and fuel_liters > 0:
            gen_rate_kw    = self.generator_capacity_kw
            usable_gen_kwh = fuel_liters / self.generator_fuel_rate
        else:
            gen_rate_kw    = 0.0
            usable_gen_kwh = 0.0

        solar_kw = twin_state["solar_state"]["generation_kw"]
        crit = twin_state["load_state"]["critical_kw"]
        imp  = twin_state["load_state"]["important_kw"]
        flex = twin_state["load_state"]["flexible_kw"]

        tiers = {
            "critical_only":          crit,
            "critical_and_important": crit + imp,
            "all_loads":              crit + imp + flex,
        }

        # Maximum instantaneous supply power (exclusive of solar, which
        # is already subtracted as part of net_demand below)
        bat_power_kw  = self.battery_max_discharge_kw if usable_bat_raw_kwh > 0.0 else 0.0
        max_supply_kw = bat_power_kw + gen_rate_kw

        results: Dict[str, float] = {}
        for tier_name, tier_load_kw in tiers.items():
            net_demand_kw = tier_load_kw - solar_kw

            if net_demand_kw <= 0.0:
                # Solar alone satisfies this tier — infinite survival.
                results[f"{tier_name}_hours"] = float("inf")

            elif net_demand_kw > max_supply_kw:
                # Power constraint violated: even at maximum output the system
                # cannot supply this tier. Failure is occurring immediately.
                # ESH = 0.0 (time-to-power-failure = immediate).
                results[f"{tier_name}_hours"] = 0.0

            else:
                # Power constraint satisfied: energy-duration formula is valid.
                # Battery is assumed to discharge first, then generator sustains.
                total_available_kwh = usable_bat_kwh + usable_gen_kwh
                results[f"{tier_name}_hours"] = total_available_kwh / net_demand_kw

        return results

    def calculate_forecast_esh(
        self,
        twin_state: Dict[str, Any],
        forecast:   List[Dict[str, float]],
    ) -> Dict[str, float]:
        """
        Authoritative forward-simulation ESH for the Decision Engine.

        Simulates the energy system timestep by timestep using the provided
        forecast. Tracks battery raw stored energy and generator fuel as they
        evolve. Stops when the active tier's load cannot be fully supplied
        within the unmet tolerance.

        Dispatch order per step:
          1. Solar satisfies demand first (free energy, no storage consumed).
          2. Surplus solar charges the battery (up to charge rate and max SOC).
          3. Generator covers remaining deficit up to generator_capacity_kw.
             Fuel is consumed accordingly; generator stops when fuel is zero.
          4. Battery covers any remaining deficit up to max_discharge_kw.
             Discharge efficiency is applied (raw storage drained > delivered).
          5. If demand still unmet beyond tolerance -> survival failure recorded.

        Post-forecast extension:
          If the system survives the entire forecast window, the remaining
          energy is projected at the last step's net demand rate, subject to
          the same power constraint check.

        Returns:
            Dict with keys:
                "critical_only_hours"
                "critical_and_important_hours"
                "all_loads_hours"
        """
        dt_hours = self.timestep_minutes / 60.0

        # Snapshot starting state (each tier runs its own independent simulation)
        initial_bat_energy  = self._usable_battery_raw_kwh(twin_state["battery_state"]["soc"])
        initial_fuel        = twin_state["generator_state"]["fuel_liters"]
        initial_gen_avail   = twin_state["generator_state"].get("is_available", True)

        results: Dict[str, float] = {}

        for tier in ("critical_only", "critical_and_important", "all_loads"):
            # Per-tier simulation state
            bat_energy = initial_bat_energy
            fuel       = initial_fuel
            gen_avail  = initial_gen_avail

            hours_survived   = 0.0
            failed           = False
            last_tier_demand = 0.0
            last_solar_kw    = 0.0

            for step in forecast:
                tier_demand_kw = self._tier_demand(tier, step)
                solar_kw       = step["solar_kw"]
                last_tier_demand = tier_demand_kw
                last_solar_kw    = solar_kw

                # --- Solar satisfies demand first ---
                remaining_kw = max(0.0, tier_demand_kw - solar_kw)
                surplus_kw   = max(0.0, solar_kw - tier_demand_kw)

                # --- Surplus solar charges battery ---
                if surplus_kw > 0.0:
                    charge_kw = min(surplus_kw, self.battery_max_charge_kw)
                    energy_in = charge_kw * dt_hours * self.battery_charge_eff
                    # Room = max usable range minus current position in that range
                    bat_room  = (self.battery_capacity_kwh
                                 * (self.battery_max_soc_percent - self.battery_min_soc_percent)
                                 / 100.0) - bat_energy
                    bat_energy += min(energy_in, max(0.0, bat_room))

                # --- Generator covers remaining deficit (generator-first policy) ---
                if remaining_kw > 0.0 and gen_avail and fuel > 0.0:
                    gen_kw      = min(remaining_kw, self.generator_capacity_kw)
                    fuel_needed = gen_kw * dt_hours * self.generator_fuel_rate
                    if fuel_needed > fuel:
                        # Fuel exhausted mid-step: prorate generator output
                        gen_kw = (fuel / self.generator_fuel_rate) / dt_hours
                        fuel   = 0.0
                    else:
                        fuel -= fuel_needed
                    remaining_kw = max(0.0, remaining_kw - gen_kw)

                # --- Battery covers remaining deficit ---
                if remaining_kw > 0.0 and bat_energy > 0.0:
                    # Raw energy to draw from storage to deliver required power
                    energy_needed  = remaining_kw * dt_hours / self.battery_discharge_eff
                    max_bat_drain  = min(self.battery_max_discharge_kw * dt_hours, bat_energy)
                    actual_drain   = min(energy_needed, max_bat_drain)
                    bat_kw_out     = actual_drain * self.battery_discharge_eff / dt_hours
                    bat_energy    -= actual_drain
                    remaining_kw   = max(0.0, remaining_kw - bat_kw_out)

                # --- Check survival ---
                if remaining_kw > _UNMET_TOLERANCE_KW:
                    # Cannot fully supply this tier's demand this step
                    supplied_kw    = tier_demand_kw - remaining_kw
                    fraction       = (supplied_kw / tier_demand_kw) if tier_demand_kw > 0 else 1.0
                    hours_survived += fraction * dt_hours
                    failed         = True
                    break

                hours_survived += dt_hours

            # --- Post-forecast extension ---
            if not failed and len(forecast) > 0:
                final_net_kw = last_tier_demand - last_solar_kw

                if final_net_kw <= 0.0:
                    # Renewable surplus at forecast boundary — infinite survival.
                    hours_survived = float("inf")
                else:
                    bat_deliverable  = bat_energy * self.battery_discharge_eff
                    gen_energy_left  = (fuel / self.generator_fuel_rate
                                        if gen_avail and fuel > 0.0 else 0.0)
                    remaining_energy = bat_deliverable + gen_energy_left

                    gen_power   = self.generator_capacity_kw if (gen_avail and fuel > 0.0) else 0.0
                    max_rate_kw = self.battery_max_discharge_kw + gen_power

                    if final_net_kw > max_rate_kw:
                        # Power cap exceeded at forecast boundary.
                        # Battery drains at its maximum discharge rate until empty;
                        # after that, generator alone is insufficient → failure.
                        if self.battery_max_discharge_kw > 0.0:
                            hours_survived += bat_deliverable / self.battery_max_discharge_kw
                    else:
                        hours_survived += remaining_energy / final_net_kw

            results[f"{tier}_hours"] = hours_survived

        return results
