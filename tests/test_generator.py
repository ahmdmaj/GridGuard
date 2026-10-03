from simulator.generator import Generator

def test_generator_initial_state():
    gen = Generator()
    assert gen.is_running is False
    assert gen.is_available is True
    assert gen.fuel_liters == 100.0

def test_generator_start():
    gen = Generator()
    gen.start()
    assert gen.is_running is True

def test_generator_set_availability_forces_stop():
    gen = Generator()
    gen.start()
    assert gen.is_running is True
    gen.set_availability(False)
    assert gen.is_available is False
    assert gen.is_running is False

def test_generator_normal_generation():
    gen = Generator()
    gen.start()
    returned_power = gen.generate(10.0, 5.0)
    assert abs(returned_power - 10.0) < 1e-6
    expected_fuel_drop = (10.0 * (5.0 / 60.0)) * 0.3
    assert abs(gen.fuel_liters - (100.0 - expected_fuel_drop)) < 1e-6

def test_generator_capacity_limit():
    gen = Generator()
    gen.start()
    returned_power = gen.generate(20.0, 5.0)
    assert abs(returned_power - 15.0) < 1e-6
    expected_fuel_drop = (15.0 * (5.0 / 60.0)) * 0.3
    assert abs(gen.fuel_liters - (100.0 - expected_fuel_drop)) < 1e-6

def test_generator_fuel_starvation():
    gen = Generator()
    gen.fuel_liters = 0.1
    gen.start()
    returned_power = gen.generate(15.0, 5.0)
    # Available energy = 0.1 / 0.3 = 0.333333 kWh
    # Returned power = 0.333333 / (5/60) = 4.0 kW
    assert abs(returned_power - 4.0) < 1e-6
    assert gen.fuel_liters == 0.0
    assert gen.is_running is False
