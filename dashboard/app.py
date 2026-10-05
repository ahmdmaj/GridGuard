import streamlit as st
import datetime
import pandas as pd
import sys
import os
import time

# Ensure the root project directory is in the Python path
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from physical.plant import PhysicalPlant
from physical.feeder import SagEvent
from intelligence.decision_engine import DecisionEngine
from metrics.esh import ESHCalculator
from digital_twin.state import DigitalTwinState, GridState, SolarState, BatteryState, GeneratorState, LoadState
from forecasting.service import MLForecastService

st.set_page_config(page_title="GridGuard V2 Dashboard", layout="wide")

st.title("GridGuard Digital Twin & IoT Simulation")
st.markdown("Phase 1: Peak-hour under-voltage protection and outage survival.")

# --- STEP 1: STRICT STATE INITIALIZATION ---
start_dt = datetime.datetime(2026, 1, 1, 12, 0, 0)
end_time = start_dt + datetime.timedelta(hours=12)
dt_s = 60.0 # 1 minute steps

if "initialized" not in st.session_state:
    config = {
        "z_pu": 0.1,
        "p_feeder_rating_kw": 500.0,
        "bg_peak_kw": 500.0,
        "noise_sigma_pu": 0.002,
        "inverter_rating_kw": 20.0,
        "battery_capacity_kwh": 40.0,
        "generator_capacity_kw": 15.0,
        "critical_kw": 4.0,
        "important_kw": 3.0,
        "non_essential_kw": 2.0,
        "generator_start_esh_hours": 2.0,
        "generator_stop_soc": 50.0,
    }
    
    st.session_state.plant = PhysicalPlant(config)
    st.session_state.controller = DecisionEngine(config)
    st.session_state.esh_calc = ESHCalculator(config)
    st.session_state.forecast = MLForecastService()
    
    st.session_state.current_time = start_dt
    st.session_state.is_running = False
    st.session_state.history = []
    st.session_state.initialized = True

# --- STEP 2: INTERACTIVE SIDEBAR (LIVE INJECTIONS) ---
st.sidebar.header("Live Demonstration Controls")

# 1. Grid Outage Controller
grid_outage = st.sidebar.toggle("🚨 Trigger Grid Outage", value=False)

# 2. Voltage Adjusting Controller
# Disabled if grid is fully out
grid_voltage = st.sidebar.slider("⚡ Live Grid Voltage (pu)", 0.0, 1.1, 1.0, disabled=grid_outage)

# 3. Day / Night Controller
time_of_day = st.sidebar.radio("☀️ Time of Day", ["Day (High Solar)", "Night (Zero Solar)"])

# --- STEP 3: TOP CONTROL BUTTONS ---
col1, col2, col3 = st.columns(3)
if col1.button("▶ Start/Resume Live Simulation", type="primary"):
    st.session_state.is_running = True
if col2.button("⏸ Pause Simulation"):
    st.session_state.is_running = False
if col3.button("🔄 Reset Simulation"):
    st.session_state.is_running = False
    st.session_state.current_time = start_dt
    st.session_state.history = []
    
    # Reinitialize physics
    config = {
        "z_pu": 0.1,
        "p_feeder_rating_kw": 500.0,
        "bg_peak_kw": 500.0,
        "noise_sigma_pu": 0.002,
        "inverter_rating_kw": 20.0,
        "battery_capacity_kwh": 40.0,
        "generator_capacity_kw": 15.0,
        "critical_kw": 4.0,
        "important_kw": 3.0,
        "non_essential_kw": 2.0,
        "generator_start_esh_hours": 2.0,
        "generator_stop_soc": 50.0,
    }
    st.session_state.plant = PhysicalPlant(config)
    st.session_state.controller = DecisionEngine(config)
    st.session_state.esh_calc = ESHCalculator(config)
    st.session_state.forecast = MLForecastService()
    st.rerun()

# --- STEP 4: EXECUTION TICK & CHART RENDERING ---
if st.session_state.is_running and st.session_state.current_time < end_time:
    plant = st.session_state.plant
    
    # Apply Grid Outage & Voltage Control
    if grid_outage:
        plant.feeder.sag_events = [SagEvent(st.session_state.current_time, 999999, 1.0)]
    else:
        plant.feeder.sag_events = [SagEvent(st.session_state.current_time, 999999, 1.0 - grid_voltage)]

    # Apply Day/Night Control (Solar Override ONLY)
    if time_of_day == "Day (High Solar)":
        plant.solar.get_generation = lambda *args: 25.0 # INCREASED: Creates a massive surplus to charge battery
        st.session_state.forecast.override_hour = 12
    else:
        plant.solar.get_generation = lambda *args: 0.0 # Force physical night
        st.session_state.forecast.override_hour = 20

    current_time = st.session_state.current_time
    controller = st.session_state.controller
    esh_calc = st.session_state.esh_calc
    forecast_svc = st.session_state.forecast
    
    # 2. SYNC DIGITAL TWIN (Before Step)
    # Generate telemetry inline to avoid Streamlit module caching issues
    preview_v_pcc = max(0.0, plant.feeder.get_voltage_pu(current_time, plant.last_p_site_kw))
    
    telemetry_snapshot = {
        "ts": current_time.isoformat() + "Z",
        "v_rms_pu": preview_v_pcc,
        "grid_connected": not grid_outage,
        "soc": plant.battery.soc,
        "fuel_liters": plant.generator.fuel_liters,
        "gen_available": plant.generator.is_available,
        "solar_kw": plant.solar.get_generation()
    }
    
    is_comms_healthy = True
        
    cmd = None
    if is_comms_healthy:
        twin_state = DigitalTwinState(
            timestamp=telemetry_snapshot["ts"],
            grid=GridState(voltage_pu=telemetry_snapshot["v_rms_pu"], is_available=telemetry_snapshot["grid_connected"]),
            solar=SolarState(power_kw=telemetry_snapshot["solar_kw"]),
            battery=BatteryState(soc=telemetry_snapshot["soc"]),
            generator=GeneratorState(fuel_liters=telemetry_snapshot["fuel_liters"], is_available=telemetry_snapshot["gen_available"]),
            loads=LoadState(critical_kw=4.0, important_kw=3.0, flexible_kw=2.0)
        )
        
        forecast = forecast_svc.generate_forecast(twin_state, 12*12) # 12 hours * 12 (5-min intervals)
        
        expected_esh = esh_calc.calculate_forecast_esh(twin_state, forecast, assume_island=False)
        shadow_esh = esh_calc.calculate_forecast_esh(twin_state, forecast, assume_island=True)
        
        # 3. AI MAKES DECISION
        cmd = controller.evaluate(dt_s, (current_time - start_dt).total_seconds(), telemetry_snapshot, expected_esh, shadow_esh)
        
        # DEMO OVERRIDE: Never shed Important Loads (Tier 2). Cap shedding at Tier 1 (Flexible only).
        if cmd and cmd.get("shed_tier", 0) == 2:
            cmd["shed_tier"] = 1
    else:
        expected_esh = {"critical_only_hours": 0}
        shadow_esh = {"critical_only_hours": 0}

    # 4. EXECUTE PHYSICS
    res = plant.step(dt_s, current_time, cmd)
    telem = res["plant_telem"]
    
    # 5. SAVE HISTORY
    st.session_state.history.append({
        "Time": current_time,
        "V_PCC (pu)": telem["v_rms_pu"],
        "V_Critical (pu)": telem["v_crit_pu"],
        "SOC (%)": telem["soc"],
        "Mode": telem["sts_state"],
        "Critical Load (kW)": telem["load_critical_kw"],
        "Important Load (kW)": telem["load_important_kw"],
        "Flexible Load (kW)": telem["load_flexible_kw"],
        "ESH (h)": expected_esh.get("critical_only_hours", 0.0),
        "Gen Status": "RUNNING" if telem["gen_available"] and telem["fuel_liters"] < 100.0 else "OFF",
        "Transfers": telem["transfer_count"],
        "Reason": cmd["reason"] if cmd else "Comms Lost - Local Protection Active",
        "generator_run": plant.generator.is_running,
        "connect_flexible": plant.loads.connected["non_essential"],
        "connect_important": plant.loads.connected["important"],
        "solar_kw": telem["solar_kw"]
    })
    
    st.session_state.current_time += datetime.timedelta(seconds=dt_s)

# Render UI from history
if len(st.session_state.history) > 0:
    df = pd.DataFrame(st.session_state.history)
    df['timestamp'] = pd.to_datetime(df['Time'])
    df.set_index('timestamp', inplace=True)
    
    st.subheader("System Status")
    latest = st.session_state.history[-1]
    col_a, col_b, col_c, col_d = st.columns(4)
    with col_a:
        gen_status = "🟢 ON" if latest.get("generator_run", False) else "⚪ OFF"
        st.metric("Generator", gen_status)
    with col_b:
        solar_val = latest.get("solar_kw", 0.0)
        solar_status = f"🟢 ACTIVE" if solar_val > 0 else "⚪ OFF"
        st.metric("Solar Array", solar_status)
    with col_c:
        flex_status = "🔴 SHED" if not latest.get("connect_flexible", True) else "🟢 ACTIVE"
        st.metric("Flexible Loads", flex_status)
    with col_d:
        imp_status = "🔴 SHED" if not latest.get("connect_important", True) else "🟢 ACTIVE"
        st.metric("Important Loads", imp_status)
        
    st.subheader("Live Metrics")
    col1, col2, col3, col4, col5 = st.columns(5)
    col1.metric("Current Time", st.session_state.current_time.strftime("%H:%M"))
    col2.metric("Min V_Critical", f"{df['V_Critical (pu)'].min():.3f} pu")
    col3.metric("Transfers", df["Transfers"].iloc[-1])
    col4.metric("Current SOC", f"{df['SOC (%)'].iloc[-1]:.1f}%")
    col5.metric("Unmet Critical", f"{st.session_state.plant.unserved_kw:.1f} kW")
    
    col_v, col_soc = st.columns(2)
    with col_v:
        st.subheader("Voltage Profile")
        st.line_chart(df[["V_PCC (pu)", "V_Critical (pu)"]])
    with col_soc:
        st.subheader("Battery SOC (%)")
        st.line_chart(df[["SOC (%)"]])
        
    st.subheader("Load Profile (kW)")
    st.area_chart(df[["Critical Load (kW)", "Important Load (kW)", "Flexible Load (kW)"]])
    
    st.subheader("Decision Engine Log")
    st.dataframe(df[["Time", "Mode", "ESH (h)", "Reason"]].iloc[::-1].head(10))

# --- STEP 5: THE ANIMATION LOOP ---
if st.session_state.is_running and st.session_state.current_time < end_time:
    time.sleep(0.05)
    st.rerun()
elif st.session_state.is_running and st.session_state.current_time >= end_time:
    st.session_state.is_running = False



