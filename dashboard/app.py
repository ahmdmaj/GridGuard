import streamlit as st
import datetime
import pandas as pd
import sys
import os

# Ensure the root project directory is in the Python path
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from physical.plant import PhysicalPlant
from physical.feeder import SagEvent
from intelligence.decision_engine import DecisionEngine
from intelligence.esh import ESHCalculator
from experiments.run_scenarios import generate_rule_forecast

st.set_page_config(page_title="GridGuard V2 Dashboard", layout="wide")

st.title("GridGuard Digital Twin & IoT Simulation")
st.markdown("Phase 1: Peak-hour under-voltage protection and outage survival.")

# --- SIDEBAR INPUTS ---
st.sidebar.header("Scenario Parameters")
bg_peak_kw = st.sidebar.slider("Peak Background Load (kW)", 200.0, 800.0, 500.0, 50.0)
sag_depth = st.sidebar.slider("Sag Depth (pu)", 0.0, 1.0, 0.1, 0.05)
sag_duration_s = st.sidebar.slider("Sag Duration (s)", 0.0, 7200.0, 3600.0, 300.0)
comms_loss = st.sidebar.checkbox("Inject MQTT Comms Loss (18:00 - 20:00)", False)

st.sidebar.header("Physical Plant")
z_pu = st.sidebar.slider("Feeder Impedance (Z pu)", 0.01, 0.2, 0.1, 0.01)
battery_capacity_kwh = st.sidebar.slider("Battery Capacity (kWh)", 10.0, 100.0, 40.0, 10.0)
inverter_rating_kw = st.sidebar.slider("Inverter Rating (kW)", 5.0, 50.0, 20.0, 5.0)

st.sidebar.header("Controller Settings")
gen_start_esh = st.sidebar.slider("Generator Start ESH (hours)", 0.5, 5.0, 2.0, 0.5)

# --- RUN SIMULATION ---
config = {
    "z_pu": z_pu,
    "p_feeder_rating_kw": 500.0,
    "bg_peak_kw": bg_peak_kw,
    "noise_sigma_pu": 0.002,
    "inverter_rating_kw": inverter_rating_kw,
    "battery_capacity_kwh": battery_capacity_kwh,
    "generator_capacity_kw": 15.0,
    "critical_kw": 4.0,
    "important_kw": 3.0,
    "non_essential_kw": 2.0,
    "generator_start_esh_hours": gen_start_esh,
}

plant = PhysicalPlant(config)
controller = DecisionEngine(config)
esh_calc = ESHCalculator(config)

start_dt = datetime.datetime(2026, 1, 1, 12, 0, 0)
if sag_depth > 0 and sag_duration_s > 0:
    # Inject sag at 19:00 (peak hour)
    plant.feeder.add_sag_event(SagEvent(start_dt + datetime.timedelta(hours=7), sag_duration_s, sag_depth))

current_time = start_dt
dt_s = 60.0 # 1 minute steps for fast dashboard rendering
end_time = start_dt + datetime.timedelta(hours=12)

results = []

while current_time < end_time:
    telemetry = {
        "ts": current_time.isoformat() + "Z",
        "v_rms_pu": plant.v_pcc_pu,
        "grid_connected": True,
        "soc": plant.battery.soc,
        "fuel_liters": plant.generator.fuel_liters,
        "gen_available": True
    }
    
    is_comms_healthy = True
    if comms_loss and current_time.hour >= 18 and current_time.hour < 20:
        is_comms_healthy = False
        
    cmd = None
    if is_comms_healthy:
        forecast = generate_rule_forecast(current_time, 12*3600, 300)
        expected_esh = esh_calc.calculate_forecast_esh(telemetry, forecast, assume_island=False)
        shadow_esh = esh_calc.calculate_forecast_esh(telemetry, forecast, assume_island=True)
        cmd = controller.evaluate(dt_s, (current_time - start_dt).total_seconds(), telemetry, expected_esh, shadow_esh)
    else:
        expected_esh = {"critical_only_hours": 0}
        shadow_esh = {"critical_only_hours": 0}

    res = plant.step(dt_s, current_time, cmd)
    telem = res["plant_telem"]
    
    results.append({
        "Time": current_time,
        "V_PCC (pu)": telem["v_rms_pu"],
        "V_Critical (pu)": telem["v_crit_pu"],
        "SOC (%)": telem["soc"],
        "Mode": telem["sts_state"],
        "Critical Load (kW)": telem["load_critical_kw"],
        "Important Load (kW)": telem["load_important_kw"],
        "Flexible Load (kW)": telem["load_flexible_kw"],
        "ESH (h)": expected_esh.get("critical_only_hours", 0.0),
        "Gen Status": "RUNNING" if telem["gen_available"] and telem["fuel_liters"] < 100.0 else "OFF", # Hacky status
        "Transfers": telem["transfer_count"],
        "Reason": cmd["reason"] if cmd else "Comms Lost - Local Protection Active"
    })
    
    current_time += datetime.timedelta(seconds=dt_s)

df = pd.DataFrame(results)

# --- VISUALIZATION ---
col1, col2, col3, col4 = st.columns(4)
col1.metric("Min V_Critical", f"{df['V_Critical (pu)'].min():.3f} pu")
col2.metric("Transfers", df["Transfers"].iloc[-1])
col3.metric("Min SOC", f"{df['SOC (%)'].min():.1f}%")
col4.metric("Unmet Critical", f"{plant.unserved_kw:.1f} kW") # Simplistic

st.subheader("Voltage Profile")
st.line_chart(df.set_index("Time")[["V_PCC (pu)", "V_Critical (pu)"]])
# st.markdown("Note: The ±6% statutory band is [0.94, 1.06] pu.")

st.subheader("Battery SOC & Load Profile")
st.line_chart(df.set_index("Time")[["SOC (%)"]])
st.area_chart(df.set_index("Time")[["Critical Load (kW)", "Important Load (kW)", "Flexible Load (kW)"]])

st.subheader("Decision Engine Log")
st.dataframe(df[["Time", "Mode", "ESH (h)", "Reason"]].iloc[::15]) # Show every 15 mins
