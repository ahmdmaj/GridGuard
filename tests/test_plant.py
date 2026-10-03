from simulator.plant import PhysicalPlant
from simulator.constants import LoadCategory

def test_plant_normal_grid_operation():
    plant = PhysicalPlant()
    plant.step()
    assert plant.current_load_kw == -10.0
    assert plant.current_grid_kw == 10.0
    assert plant.current_unserved_kw == 0.0
    assert plant.current_solar_kw == 0.0
    assert plant.current_batt_kw == 0.0
    assert plant.current_gen_kw == 0.0

def test_plant_solar_export():
    plant = PhysicalPlant()
    # Disconnect all loads
    for cat in LoadCategory:
        plant.load.set_connection(cat, False)
    
    plant.solar.set_availability(1.0)
    plant.step()
    
    assert plant.current_load_kw == 0.0
    assert plant.current_solar_kw == 10.0
    assert plant.current_grid_kw == -10.0
    assert plant.current_unserved_kw == 0.0

def test_plant_grid_outage_unserved():
    plant = PhysicalPlant()
    plant.grid.fail()
    plant.step()
    
    assert plant.current_load_kw == -10.0
    assert plant.current_grid_kw == 0.0
    assert plant.current_unserved_kw == 10.0
    assert plant.current_gen_kw == 0.0
    assert plant.current_batt_kw == 0.0

def test_plant_grid_outage_with_generator():
    plant = PhysicalPlant()
    plant.grid.fail()
    plant.generator.start()
    plant.step()
    
    assert plant.current_load_kw == -10.0
    assert plant.current_grid_kw == 0.0
    assert plant.current_gen_kw == 10.0
    assert plant.current_unserved_kw == 0.0

def test_plant_battery_discharge_support():
    plant = PhysicalPlant()
    plant.grid.fail()
    # No generator running by default
    plant.step(battery_command_kw=10.0)
    
    assert plant.current_load_kw == -10.0
    assert plant.current_batt_kw == 10.0
    assert plant.current_grid_kw == 0.0
    assert plant.current_gen_kw == 0.0
    assert plant.current_unserved_kw == 0.0
