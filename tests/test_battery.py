from simulator.battery import Battery

def test_battery_initial_state():
    batt = Battery()
    assert batt.soc == 100.0
    assert batt.current_energy_kwh == 40.0

def test_battery_normal_discharge():
    batt = Battery()
    power_delivered = batt.discharge(10.0, 5.0)
    # Delivered should be exactly 10.0
    assert abs(power_delivered - 10.0) < 1e-6
    # Drained energy = (10 * 5/60) / 0.95 = 0.87719...
    expected_drain = (10.0 * (5.0 / 60.0)) / 0.95
    assert abs(batt.current_energy_kwh - (40.0 - expected_drain)) < 1e-6

def test_battery_normal_charge():
    batt = Battery()
    batt.current_energy_kwh = 20.0
    power_absorbed = batt.charge(10.0, 5.0)
    assert abs(power_absorbed - 10.0) < 1e-6
    # Stored energy = 10 * (5/60) * 0.95 = 0.791666...
    expected_store = 10.0 * (5.0 / 60.0) * 0.95
    assert abs(batt.current_energy_kwh - (20.0 + expected_store)) < 1e-6

def test_battery_charge_limit():
    batt = Battery()
    batt.current_energy_kwh = 20.0
    power_absorbed = batt.charge(30.0, 5.0)
    assert abs(power_absorbed - 20.0) < 1e-6

def test_battery_soc_maximum_boundary():
    batt = Battery()
    power_absorbed = batt.charge(10.0, 5.0)
    assert abs(power_absorbed - 0.0) < 1e-6
    assert batt.soc == 100.0
    assert batt.current_energy_kwh == 40.0

def test_battery_soc_minimum_boundary():
    batt = Battery()
    # Min SOC is 20% -> 8 kWh
    batt.current_energy_kwh = 8.1
    power_delivered = batt.discharge(20.0, 5.0)
    # Available energy = 0.1 kWh
    # power_delivered should be bounded by available energy
    # drained_energy = 0.1
    # returned power = 0.1 * 0.95 / (5/60) = 1.14 kW
    assert abs(batt.current_energy_kwh - 8.0) < 1e-6
    assert abs(power_delivered - (0.1 * 0.95 / (5.0 / 60.0))) < 1e-6
