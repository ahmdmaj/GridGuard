from simulator.load import BuildingLoad
from simulator.constants import LoadCategory

def test_load_initial_state():
    load = BuildingLoad()
    for cat in LoadCategory:
        assert load.is_connected[cat] is True
    assert load.get_total_demand_kw() == 10.0
    assert load.get_demand_by_category(LoadCategory.CRITICAL) == 3.0
    assert load.get_demand_by_category(LoadCategory.IMPORTANT) == 3.0
    assert load.get_demand_by_category(LoadCategory.FLEXIBLE) == 4.0

def test_load_shedding():
    load = BuildingLoad()
    load.set_connection(LoadCategory.FLEXIBLE, False)
    assert load.get_demand_by_category(LoadCategory.FLEXIBLE) == 0.0
    assert load.get_total_demand_kw() == 6.0

def test_load_demand_scaling():
    load = BuildingLoad()
    load.set_demand_multiplier(1.5)
    assert load.get_total_demand_kw() == 15.0
    assert load.get_demand_by_category(LoadCategory.CRITICAL) == 4.5
    assert load.get_demand_by_category(LoadCategory.IMPORTANT) == 4.5
    assert load.get_demand_by_category(LoadCategory.FLEXIBLE) == 6.0

def test_load_combined_logic():
    load = BuildingLoad()
    load.set_demand_multiplier(2.0)
    load.set_connection(LoadCategory.IMPORTANT, False)
    load.set_connection(LoadCategory.FLEXIBLE, False)
    assert load.get_total_demand_kw() == 6.0
    assert load.get_demand_by_category(LoadCategory.CRITICAL) == 6.0
    assert load.get_demand_by_category(LoadCategory.IMPORTANT) == 0.0
    assert load.get_demand_by_category(LoadCategory.FLEXIBLE) == 0.0
