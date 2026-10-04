import pytest
import datetime
from physical.plant import PhysicalPlant

def test_energy_balance():
    # T-ENERGY
    config = {
        "generator_capacity_kw": 15.0,
        "battery_capacity_kwh": 40.0,
        "watchdog_s": 90.0
    }
    plant = PhysicalPlant(config)
    start_dt = datetime.datetime(2026, 1, 1, 12, 0, 0)
    
    # Run a few steps with known commands
    # Charge battery, run generator, serve load
    dt_s = 60.0
    
    plant.battery.current_energy_kwh = 20.0
    initial_batt_kwh = plant.battery.current_energy_kwh
    
    # 1 hr simulation
    total_grid_import_kwh = 0.0
    total_solar_kwh = 0.0
    total_gen_kwh = 0.0
    total_load_kwh = 0.0
    total_unserved_kwh = 0.0
    total_batt_ac_kwh = 0.0
    
    for i in range(60):
        current_time = start_dt + datetime.timedelta(seconds=i*dt_s)
        cmd = {"inverter_mode": "SUPPORT", "shed_tier": 0, "gen_cmd": "START", "charge_limit_kw": 5.0}
        res = plant.step(dt_s, current_time, cmd)
        
        # Power is in kW, energy is kW * (dt_s / 3600.0)
        h = dt_s / 3600.0
        
        # Determine grid import. If last_p_site_kw > 0, it's import.
        if plant.last_p_site_kw > 0:
            total_grid_import_kwh += plant.last_p_site_kw * h
            
        total_solar_kwh += plant.solar_kw * h
        total_gen_kwh += plant.gen_kw * h
        total_load_kwh += plant.load_kw * h
        total_unserved_kwh += plant.unserved_kw * h
        total_batt_ac_kwh += plant.batt_kw * h
        
    final_batt_kwh = plant.battery.soc / 100.0 * plant.battery.capacity_kwh
    
    # Net Energy = (grid_in + solar + gen) - load_served + batt_ac_kwh
    # (batt_kw is positive when discharging, negative when charging)
    net_energy_error = (total_grid_import_kwh + total_solar_kwh + total_gen_kwh) - total_load_kwh + total_batt_ac_kwh
    assert abs(net_energy_error) < 0.1, f"Energy conservation failed! Error = {net_energy_error:.3f} kWh"
    
    # T-FUEL
    total_fuel_used = 100.0 - plant.generator.fuel_liters
    if total_gen_kwh > 0:
        avg_gen_kw = total_gen_kwh / 1.0 # 1 hour
        l_per_kwh = total_fuel_used / total_gen_kwh
        print(f"DEBUG: fuel={total_fuel_used:.3f}, gen={total_gen_kwh:.3f}, L/kWh={l_per_kwh:.3f}, avg_gen_kw={avg_gen_kw:.3f}")
        if avg_gen_kw > 0.2 * plant.generator.capacity_kw:
            assert 0.2 <= l_per_kwh <= 1.0, f"Fuel efficiency {l_per_kwh:.2f} L/kWh is outside plausible band!"
        
    print(f"L/kWh: {total_fuel_used / total_gen_kwh if total_gen_kwh > 0 else 0}")
