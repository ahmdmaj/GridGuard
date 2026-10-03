from simulator.solar import SolarPV

def test_solar_initial_state():
    solar = SolarPV()
    assert solar.capacity_kw == 10.0
    assert solar.availability_factor == 0.0
    assert solar.get_generation() == 0.0

def test_solar_set_availability_full():
    solar = SolarPV()
    solar.set_availability(1.0)
    assert solar.availability_factor == 1.0
    assert solar.get_generation() == 10.0

def test_solar_set_availability_half():
    solar = SolarPV()
    solar.set_availability(0.5)
    assert solar.availability_factor == 0.5
    assert solar.get_generation() == 5.0

def test_solar_clamping_upper():
    solar = SolarPV()
    solar.set_availability(1.5)
    assert solar.availability_factor == 1.0
    assert solar.get_generation() == 10.0

def test_solar_clamping_lower():
    solar = SolarPV()
    solar.set_availability(-0.2)
    assert solar.availability_factor == 0.0
    assert solar.get_generation() == 0.0

def test_solar_custom_capacity():
    solar = SolarPV(capacity_kw=20.0)
    solar.set_availability(0.5)
    assert solar.availability_factor == 0.5
    assert solar.get_generation() == 10.0
