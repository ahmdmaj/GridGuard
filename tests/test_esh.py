"""
tests/test_esh.py — ESH Calculator Test Suite (Phase A Corrected)

All tests in this file are derived from physics-correct worked examples.
The key numbers are documented inline so they can be independently verified.

Dispatch order used by calculate_forecast_esh:
    Solar -> Generator -> Battery  (optimistic / generator-first policy)

Physical constants assumed (matching simulator defaults):
    battery_capacity_kwh     = 40.0
    battery_min_soc_percent  = 20.0
    battery_max_soc_percent  = 100.0
    battery_max_charge_kw    = 20.0
    battery_max_discharge_kw = 20.0
    battery_charge_eff       = 0.95
    battery_discharge_eff    = 0.95
    generator_capacity_kw    = 15.0
    generator_fuel_rate      = 0.3   L/kWh
    timestep_minutes         = 5

dt_hours = 5 / 60 = 0.08333 hours
"""
import math
import pytest
from metrics.esh import ESHCalculator


# ---------------------------------------------------------------------------
# Shared fixture helpers
# ---------------------------------------------------------------------------

from digital_twin.state import DigitalTwinState, GridState, SolarState, BatteryState, GeneratorState, LoadState

def base_state(
    soc: float = 0.0,
    solar_kw: float = 0.0,
    crit_kw: float = 0.0,
    imp_kw: float = 0.0,
    flex_kw: float = 0.0,
    fuel_liters: float = 0.0,
    gen_available: bool = False,
) -> DigitalTwinState:
    """Build a minimal DigitalTwinState object with explicit defaults for every field."""
    return DigitalTwinState(
        grid=GridState(),
        solar=SolarState(power_kw=solar_kw),
        battery=BatteryState(soc=soc),
        generator=GeneratorState(fuel_liters=fuel_liters, is_available=gen_available),
        loads=LoadState(critical_kw=crit_kw, important_kw=imp_kw, flexible_kw=flex_kw)
    )


def flat_forecast(
    steps: int,
    solar_kw: float = 0.0,
    crit_kw:  float = 0.0,
    imp_kw:   float = 0.0,
    flex_kw:  float = 0.0,
) -> list:
    """Return a forecast list with identical demand/solar every step."""
    return [
        {
            "solar_kw":          solar_kw,
            "load_critical_kw":  crit_kw,
            "load_important_kw": imp_kw,
            "load_flexible_kw":  flex_kw,
        }
        for _ in range(steps)
    ]


# ---------------------------------------------------------------------------
# INSTANTANEOUS ESH TESTS
# ---------------------------------------------------------------------------

class TestInstantaneousESH:

    # ------------------------------------------------------------------
    # Test A — Surplus solar → infinite survival for all tiers
    # ------------------------------------------------------------------
    def test_surplus_solar_returns_inf_for_all_tiers(self):
        """
        solar = 10 kW, all-load demand = 4+3+2 = 9 kW.
        Solar exceeds every tier → net_demand <= 0 for all → inf.

        Note: gen_available=False and fuel=0 are set explicitly so the test
        is not accidentally passing due to a default generator assumption.
        """
        calc  = ESHCalculator()
        state = base_state(soc=0.0, solar_kw=10.0,
                           crit_kw=4.0, imp_kw=3.0, flex_kw=2.0,
                           fuel_liters=0.0, gen_available=False)

        result = calc.calculate_instantaneous_esh(state)

        assert math.isinf(result["critical_only_hours"])
        assert math.isinf(result["critical_and_important_hours"])
        assert math.isinf(result["all_loads_hours"])

    # ------------------------------------------------------------------
    # Test B — Battery only, no generator, no solar; efficiency applied
    # ------------------------------------------------------------------
    def test_battery_only_applies_discharge_efficiency(self):
        """
        soc = 100 %  →  raw_usable = (100-20)/100 × 40 = 32.0 kWh
        deliverable  = 32.0 × 0.95 = 30.4 kWh
        critical = 4 kW, no solar, no generator.
        Power check: net=4, max_supply=20 → satisfied.
        ESH = 30.4 / 4.0 = 7.6 hours.
        """
        calc  = ESHCalculator()
        state = base_state(soc=100.0, crit_kw=4.0,
                           gen_available=False, fuel_liters=0.0)

        result = calc.calculate_instantaneous_esh(state)

        assert math.isclose(result["critical_only_hours"], 7.6, rel_tol=0.01)

    # ------------------------------------------------------------------
    # Test C — Demand exceeds max_supply → ESH = 0.0 (immediate failure)
    # ------------------------------------------------------------------
    def test_power_cap_exceeded_returns_zero(self):
        """
        critical = 40 kW.
        max_supply = battery_max_discharge(20) + generator_capacity(15) = 35 kW.
        40 > 35 → power constraint violated → ESH = 0.0.

        The system cannot supply 40 kW continuously even for a single timestep.
        Returning 0.0 signals "time-to-power-failure = immediate" to the
        decision engine so it triggers maximum load shedding.

        (Correction applied: the original design proposed a battery-drain formula
        for this case, but that formula requires battery_drain_rate = 40-15 = 25 kW,
        which itself exceeds the battery's 20 kW discharge limit — making the
        formula self-contradictory. ESH = 0.0 is the correct and unambiguous
        representation of immediate power failure.)
        """
        calc  = ESHCalculator()
        state = base_state(soc=100.0, crit_kw=40.0,
                           gen_available=True, fuel_liters=100.0)

        result = calc.calculate_instantaneous_esh(state)

        assert result["critical_only_hours"] == 0.0

    # ------------------------------------------------------------------
    # Test D — Power cap satisfied; battery + generator formula valid
    # ------------------------------------------------------------------
    def test_power_cap_satisfied_uses_energy_formula(self):
        """
        soc = 100 %  →  deliverable = 32 × 0.95 = 30.4 kWh
        gen: capacity=15 kW, fuel=30 L → gen_kwh = 30/0.3 = 100 kWh
        critical = 5 kW (< 15 kW gen cap, power satisfied).
        total = 30.4 + 100 = 130.4 kWh
        ESH = 130.4 / 5.0 = 26.08 hours.
        """
        calc  = ESHCalculator()
        state = base_state(soc=100.0, crit_kw=5.0,
                           gen_available=True, fuel_liters=30.0)

        result = calc.calculate_instantaneous_esh(state)

        assert math.isclose(result["critical_only_hours"], 26.08, rel_tol=0.01)

    # ------------------------------------------------------------------
    # Test K — Demand exactly at power boundary; formula still valid
    # ------------------------------------------------------------------
    def test_demand_at_exact_power_boundary(self):
        """
        critical = 35 kW = battery_max_discharge(20) + generator_capacity(15).
        Power constraint: 35 <= 35 → satisfied (boundary condition).
        total = 30.4 + 100 = 130.4 kWh
        ESH = 130.4 / 35 = 3.726 hours.
        """
        calc  = ESHCalculator()
        state = base_state(soc=100.0, crit_kw=35.0,
                           gen_available=True, fuel_liters=30.0)

        result = calc.calculate_instantaneous_esh(state)

        expected = 130.4 / 35.0   # ≈ 3.726
        assert math.isclose(result["critical_only_hours"], expected, rel_tol=0.01)

    # ------------------------------------------------------------------
    # Test — Generator unavailable: fuel not counted
    # ------------------------------------------------------------------
    def test_generator_unavailable_fuel_ignored(self):
        """
        gen_available=False with 100 L of fuel.
        Generator must NOT contribute to ESH.
        soc=50 % → raw=12.0 kWh, deliverable=11.4 kWh.
        critical=3 kW, power satisfied (max_supply=20 kW bat-only).
        ESH = 11.4 / 3.0 = 3.8 hours.
        """
        calc  = ESHCalculator()
        state = base_state(soc=50.0, crit_kw=3.0,
                           gen_available=False, fuel_liters=100.0)

        result = calc.calculate_instantaneous_esh(state)

        assert math.isclose(result["critical_only_hours"], 3.8, rel_tol=0.01)

    # ------------------------------------------------------------------
    # Test — Battery at minimum SOC contributes zero energy
    # ------------------------------------------------------------------
    def test_battery_at_min_soc_contributes_zero(self):
        """
        soc = 20 % (exactly at minimum) → raw_usable = 0 kWh.
        No generator, no solar. ESH = 0 / demand = 0 hours.

        When both bat_power and gen_power are zero and net_demand > 0,
        max_supply = 0 < net_demand → ESH = 0.0 (power cap exceeded).
        """
        calc  = ESHCalculator()
        state = base_state(soc=20.0, crit_kw=3.0,
                           gen_available=False, fuel_liters=0.0)

        result = calc.calculate_instantaneous_esh(state)

        assert result["critical_only_hours"] == 0.0


# ---------------------------------------------------------------------------
# FORECAST ESH TESTS
# ---------------------------------------------------------------------------

class TestForecastESH:

    # ------------------------------------------------------------------
    # Test E — Battery depletion with discharge efficiency applied
    # ------------------------------------------------------------------
    def test_battery_depletion_applies_discharge_efficiency(self):
        """
        soc = 32.5 %  →  raw_usable = (32.5-20)/100 × 40 = 5.0 kWh
        No generator, no solar. critical = 12 kW. 3-step forecast.

        Each step drains: 12 × dt / 0.95 = 12 × 0.08333 / 0.95 = 1.0526 kWh/step
        max_bat_drain per step = min(20 × 0.08333, 5.0) = 1.6667 kWh → not limiting.

        4 full steps drain 4 × 1.0526 = 4.2105 kWh; remaining = 0.7895 kWh.
        (Forecast only has 3 steps — post-forecast extension handles the rest.)

        After 3 steps: bat = 5.0 - 3×1.0526 = 1.8421 kWh, hours = 0.25
        Post-forecast: deliverable = 1.8421×0.95 = 1.75 kWh
        Extension = 1.75 / 12 = 0.1458 hours
        Total = 0.25 + 0.1458 = 0.3958 hours

        Previous (wrong) answer: 5.0/12.0 = 0.4167  (efficiency ignored)
        Correct answer:          ≈ 0.3958
        """
        calc     = ESHCalculator()
        state    = base_state(soc=32.5, crit_kw=0.0,  # demand set in forecast
                              gen_available=False, fuel_liters=0.0)
        forecast = flat_forecast(3, crit_kw=12.0)

        result = calc.calculate_forecast_esh(state, forecast)

        assert math.isclose(result["critical_only_hours"], 0.3958, abs_tol=0.01)

    # ------------------------------------------------------------------
    # Test F — Surplus solar charges battery, extending survival
    # ------------------------------------------------------------------
    def test_surplus_solar_charges_battery_extends_survival(self):
        """
        soc = 30 %  →  raw = (30-20)/100 × 40 = 4.0 kWh
        No generator. 2-step forecast: [solar=8, demand=3], [solar=0, demand=3]

        Step 1 (solar surplus = 5 kW):
            charge = min(5, 20) = 5 kW
            stored = 5 × 0.08333 × 0.95 = 0.39583 kWh
            bat = 4.0 + 0.39583 = 4.39583 kWh

        Step 2 (solar = 0, demand = 3 kW):
            drain = 3 × 0.08333 / 0.95 = 0.26316 kWh
            bat = 4.39583 - 0.26316 = 4.13267 kWh
            hours = 0.16667

        Post-forecast (last_net = 3 kW):
            deliverable = 4.13267 × 0.95 = 3.926 kWh
            extension = 3.926 / 3.0 = 1.309 hours
            total = 0.16667 + 1.309 = 1.476 hours

        Without charging fix: 1.350 hours (surplus solar silently discarded).
        """
        calc  = ESHCalculator()
        state = base_state(soc=30.0, gen_available=False, fuel_liters=0.0)
        forecast = [
            {"solar_kw": 8.0, "load_critical_kw": 3.0, "load_important_kw": 0.0, "load_flexible_kw": 0.0},
            {"solar_kw": 0.0, "load_critical_kw": 3.0, "load_important_kw": 0.0, "load_flexible_kw": 0.0},
        ]

        result = calc.calculate_forecast_esh(state, forecast)

        assert math.isclose(result["critical_only_hours"], 1.476, abs_tol=0.02)

    # ------------------------------------------------------------------
    # Test G — Generator capacity limit prevents high-demand survival
    # ------------------------------------------------------------------
    def test_generator_capacity_limit_produces_short_survival(self):
        """
        soc=100 % → raw=32.0 kWh. gen: cap=15 kW, fuel=100 L.
        critical = 30 kW (exceeds generator cap).

        Dispatch per step:
            gen covers min(30, 15) = 15 kW
            remaining = 15 kW from battery
            bat drain = 15 × 0.08333 / 0.95 = 1.3158 kWh/step

        Steps until bat empty: 32.0 / 1.3158 = 24.32
        24 full steps = 2.0 hours; bat after 24 = 32 - 24×1.3158 = 0.4211 kWh

        Step 25: drain needed=1.3158, have=0.4211
            bat_kw_out = 0.4211 × 0.95 / 0.08333 = 4.799 kW
            remaining  = 30 - 15 - 4.799 = 10.201 > 0.001 → FAIL
            supplied   = 30 - 10.201 = 19.799 kW
            fraction   = 19.799/30 = 0.660
            hours += 0.660 × 0.08333 = 0.055
        Total = 2.0 + 0.055 = 2.055 hours

        Previous (wrong) answer: (32×0.95 + 333) / 30 ≈ 12.1 hours.
        """
        calc     = ESHCalculator()
        state    = base_state(soc=100.0, gen_available=True, fuel_liters=100.0)
        forecast = flat_forecast(200, crit_kw=30.0)  # enough steps to exhaust battery

        result = calc.calculate_forecast_esh(state, forecast)

        assert math.isclose(result["critical_only_hours"], 2.055, abs_tol=0.05)

    # ------------------------------------------------------------------
    # Test H — Generator fuel depletes mid-horizon; battery continues
    # ------------------------------------------------------------------
    def test_generator_fuel_depletion_hands_off_to_battery(self):
        """
        soc=100 % → raw=32.0 kWh. gen: cap=15 kW, fuel=4.5 L.
        critical = 5 kW (within gen cap, gen covers all demand).

        Gen phase:
            fuel/step = 5 × 0.08333 × 0.3 = 0.125 L
            steps with gen = floor(4.5 / 0.125) = 36 → 3.0 hours
            bat untouched (gen covers everything)

        Battery-only phase after gen exhausted:
            bat drain/step = 5 × 0.08333 / 0.95 = 0.4386 kWh
            steps until bat empty = floor(32.0 / 0.4386) = 72
            hours = 72 × 0.08333 = 6.0 hours
            bat after 72 = 32 - 72×0.4386 = 0.421 kWh

        Step 73 (bat-only):
            drain needed = 0.4386, have = 0.421
            bat_kw = 0.421×0.95/0.08333 = 4.795 kW
            remaining = 5 - 4.795 = 0.205 → FAIL
            fraction = 4.795/5 = 0.959
            hours += 0.959×0.08333 = 0.080

        Total = 3.0 + 6.0 + 0.080 = 9.08 hours
        """
        calc     = ESHCalculator()
        state    = base_state(soc=100.0, gen_available=True, fuel_liters=4.5)
        forecast = flat_forecast(200, crit_kw=5.0)

        result = calc.calculate_forecast_esh(state, forecast)

        assert math.isclose(result["critical_only_hours"], 9.08, abs_tol=0.1)

    # ------------------------------------------------------------------
    # Test I — Generator unavailable: fuel is not counted
    # ------------------------------------------------------------------
    def test_generator_unavailable_fuel_not_counted_in_forecast(self):
        """
        soc=50 % → raw=12.0 kWh. gen: is_available=False, fuel=100 L.
        critical = 3 kW. Generator MUST NOT contribute.

        bat drain/step = 3 × 0.08333 / 0.95 = 0.26316 kWh
        45 full steps = 3.75 hours; bat after 45 = 12 - 45×0.26316 = 0.158 kWh

        Step 46: drain needed=0.26316, have=0.158
            bat_kw = 0.158×0.95/0.08333 = 1.799 kW
            remaining = 3 - 1.799 = 1.201 → FAIL
            fraction = 1.799/3 = 0.5997
            hours += 0.5997×0.08333 = 0.0500

        Total ≈ 3.800 hours  (matches 11.4 kWh deliverable / 3 kW)
        """
        calc     = ESHCalculator()
        state    = base_state(soc=50.0, crit_kw=0.0,
                              gen_available=False, fuel_liters=100.0)
        forecast = flat_forecast(200, crit_kw=3.0)

        result = calc.calculate_forecast_esh(state, forecast)

        assert math.isclose(result["critical_only_hours"], 3.8, abs_tol=0.02)

    # ------------------------------------------------------------------
    # Test J — Entire forecast survived; post-forecast extension → inf
    # ------------------------------------------------------------------
    def test_survives_full_forecast_window_returns_inf(self):
        """
        soc=45 % → raw=10.0 kWh. No gen, no solar in excess.
        Forecast: 3 steps of solar=5, critical=5 → net=0 each step.
        No energy consumed. Last step: net=0 → post-forecast extension = inf.
        """
        calc     = ESHCalculator()
        state    = base_state(soc=45.0, gen_available=False, fuel_liters=0.0)
        forecast = flat_forecast(3, solar_kw=5.0, crit_kw=5.0)

        result = calc.calculate_forecast_esh(state, forecast)

        assert math.isinf(result["critical_only_hours"])

    # ------------------------------------------------------------------
    # Test — Three tiers produce different survival values
    # ------------------------------------------------------------------
    def test_three_tiers_produce_ordered_values(self):
        """
        With finite battery and no solar, critical-only should survive
        longest, all-loads shortest.
        soc=60 % → raw=16 kWh. No gen.
        crit=3, imp=3, flex=4 → total=10 kW.
        """
        calc     = ESHCalculator()
        state    = base_state(soc=60.0, gen_available=False, fuel_liters=0.0)
        forecast = flat_forecast(200, crit_kw=3.0, imp_kw=3.0, flex_kw=4.0)

        result = calc.calculate_forecast_esh(state, forecast)

        assert result["critical_only_hours"] >= result["critical_and_important_hours"]
        assert result["critical_and_important_hours"] >= result["all_loads_hours"]
        assert result["all_loads_hours"] > 0.0

    # ------------------------------------------------------------------
    # Test — Battery and generator combined sustain longer than battery alone
    # ------------------------------------------------------------------
    def test_generator_extends_survival_beyond_battery_alone(self):
        """
        Same battery SOC with and without generator.
        With generator: survival > without generator.
        soc=50 % → raw=12.0 kWh. critical=3 kW.
        """
        calc  = ESHCalculator()
        forecast = flat_forecast(300, crit_kw=3.0)

        state_no_gen  = base_state(soc=50.0, gen_available=False, fuel_liters=0.0)
        state_with_gen = base_state(soc=50.0, gen_available=True,  fuel_liters=30.0)

        esh_no_gen   = calc.calculate_forecast_esh(state_no_gen,   forecast)
        esh_with_gen = calc.calculate_forecast_esh(state_with_gen, forecast)

        assert esh_with_gen["critical_only_hours"] > esh_no_gen["critical_only_hours"]

    # ------------------------------------------------------------------
    # Test — Empty forecast returns zero survival
    # ------------------------------------------------------------------
    def test_empty_forecast_returns_zero(self):
        """With no forecast steps, no survival can be claimed."""
        calc   = ESHCalculator()
        state  = base_state(soc=100.0, gen_available=True, fuel_liters=100.0)
        result = calc.calculate_forecast_esh(state, [])

        assert result["critical_only_hours"] == 0.0
        assert result["critical_and_important_hours"] == 0.0
        assert result["all_loads_hours"] == 0.0

    # ------------------------------------------------------------------
    # Test — No demand → infinite survival
    # ------------------------------------------------------------------
    def test_zero_demand_returns_inf_in_forecast(self):
        """If all load tiers are zero, system survives indefinitely."""
        calc     = ESHCalculator()
        state    = base_state(soc=50.0, gen_available=False, fuel_liters=0.0)
        forecast = flat_forecast(10, crit_kw=0.0, imp_kw=0.0, flex_kw=0.0)

        result = calc.calculate_forecast_esh(state, forecast)

        # Solar=0, all demand=0, net=0 → post-forecast: last_net=0 → inf
        assert math.isinf(result["critical_only_hours"])

    # ------------------------------------------------------------------
    # Regression — Config overrides correctly change results
    # ------------------------------------------------------------------
    def test_custom_config_changes_results(self):
        """
        A smaller generator capacity should reduce survival versus the default.
        gen=5 kW cap (vs default 15 kW) with same fuel → less power available.
        """
        state    = base_state(soc=20.0, gen_available=True, fuel_liters=30.0)
        forecast = flat_forecast(200, crit_kw=10.0)  # demand exceeds 5 kW cap

        calc_default = ESHCalculator()
        calc_small   = ESHCalculator(config={"generator_capacity_kw": 5.0})

        esh_default = calc_default.calculate_forecast_esh(state, forecast)
        esh_small   = calc_small.calculate_forecast_esh(state, forecast)

        # Default (15 kW gen) covers 10 kW demand fully → longer survival
        # Small (5 kW gen) covers only 5 kW, battery must cover remaining 5 kW
        assert esh_default["critical_only_hours"] >= esh_small["critical_only_hours"]
