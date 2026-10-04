import datetime
from physical.plant import PhysicalPlant
from physical.feeder import SagEvent
from intelligence.baseline import BaselineController
from intelligence.decision_engine import DecisionEngine

config = {
    "z_pu": 0.1,
    "p_feeder_rating_kw": 500.0,
    "bg_peak_kw": 500.0,
    "noise_sigma_pu": 0.0,
    "inverter_rating_kw": 20.0,
    "battery_capacity_kwh": 40.0,
    "generator_capacity_kw": 15.0,
    "critical_kw": 4.0,
    "important_kw": 3.0,
    "non_essential_kw": 2.0
}
plant = PhysicalPlant(config)
start_dt = datetime.datetime(2026, 1, 1, 12, 0, 0)
plant.feeder.add_sag_event(SagEvent(start_dt + datetime.timedelta(hours=6), 4*3600, 1.0))

# Try Baseline
controller = BaselineController()

current_time = start_dt + datetime.timedelta(hours=5, minutes=45)
end_time = current_time + datetime.timedelta(minutes=20)
dt_s = 60.0

plant.time_s = (current_time - start_dt).total_seconds()
plant.v_pcc_pu = 1.0

while current_time < end_time:
    telemetry = {
        "ts": current_time.isoformat() + "Z",
        "v_rms_pu": plant.v_pcc_pu,
        "grid_connected": True,
        "soc": plant.battery.soc,
        "fuel_liters": plant.generator.fuel_liters,
        "gen_available": True
    }
    cmd = controller.evaluate(dt_s, (current_time - start_dt).total_seconds(), telemetry)
    res = plant.step(dt_s, current_time, cmd)
    telem = res["plant_telem"]
    
    print(f"[{current_time.time()}] telem v_pcc_before={telemetry['v_rms_pu']:.3f} -> cmd={cmd['inverter_mode']} -> step: v_pcc_after={telem['v_rms_pu']:.3f}, v_crit={telem['v_crit_pu']:.3f}, mode={telem['sts_state']}")
        
    current_time += datetime.timedelta(seconds=dt_s)
