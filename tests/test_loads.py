import pytest
from physical.loads import LoadModel, ZipModel

def test_zip_model_validation() -> None:
    with pytest.raises(ValueError):
        ZipModel(0.5, 0.5, 0.5)
        
    zip_m = ZipModel(0.2, 0.3, 0.5)
    assert zip_m.get_actual_power_pu(1.0) == pytest.approx(1.0)
    assert zip_m.get_actual_current_pu(1.0) == pytest.approx(1.0)

def test_constant_power_current_rises_as_voltage_falls() -> None:
    # Electronics is purely constant power
    zip_elec = ZipModel(0.0, 0.0, 1.0)
    
    i_100 = zip_elec.get_actual_current_pu(1.0)
    i_90 = zip_elec.get_actual_current_pu(0.9)
    i_80 = zip_elec.get_actual_current_pu(0.8)
    
    assert i_90 > i_100
    assert i_80 > i_90

def test_load_tier_power() -> None:
    config = {"critical_kw": 10.0, "important_kw": 5.0, "non_essential_kw": 20.0}
    load = LoadModel(config)
    
    # At nominal voltage, total power should be 35.0 kW
    assert load.get_total_power_kw(1.0) == pytest.approx(35.0)
    
    # Under voltage (0.8 pu), constant impedance load drops heavily, constant power stays
    p_08 = load.get_total_power_kw(0.8)
    
    # Critical (20% light, 80% elec): 10 * (0.2*0.64 + 0.8*1) = 10 * 0.928 = 9.28
    # Important (50% light, 50% elec): 5 * (0.5*0.64 + 0.5*1) = 5 * 0.82 = 4.1
    # Non_essential (100% hvac): 20 * (0.1*0.64 + 0.1*0.8 + 0.8) = 20 * (0.064 + 0.08 + 0.8) = 20 * 0.944 = 18.88
    # Total = 9.28 + 4.1 + 18.88 = 32.26
    assert p_08 == pytest.approx(32.26)

def test_load_shedding_reduces_power() -> None:
    config = {"critical_kw": 10.0, "important_kw": 5.0, "non_essential_kw": 20.0}
    load = LoadModel(config)
    
    p_full = load.get_total_power_kw(0.9)
    
    load.set_connection("non_essential", False)
    p_shed = load.get_total_power_kw(0.9)
    
    assert p_shed < p_full
    assert p_shed == pytest.approx(10.0 * 0.962 + 5.0 * 0.905) # Based on formula
