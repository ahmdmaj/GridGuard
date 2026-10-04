import pandas as pd
import numpy as np
import requests
import os
import datetime

# Colombo, Sri Lanka
LAT = 6.9271
LON = 79.8612

def fetch_weather_open_meteo(start_date: str, end_date: str) -> pd.DataFrame:
    """
    Fetches historical weather data from Open-Meteo ERA5 archive.
    URL: https://archive-api.open-meteo.com/v1/archive
    """
    url = "https://archive-api.open-meteo.com/v1/archive"
    params = {
        "latitude": LAT,
        "longitude": LON,
        "start_date": start_date,
        "end_date": end_date,
        "hourly": ["temperature_2m", "cloud_cover", "direct_normal_irradiance"],
        "timezone": "Asia/Colombo"
    }
    print(f"Fetching Open-Meteo data for {start_date} to {end_date}...")
    response = requests.get(url, params=params)
    response.raise_for_status()
    data = response.json()
    
    df = pd.DataFrame({
        "timestamp": pd.to_datetime(data["hourly"]["time"]),
        "temperature_c": data["hourly"]["temperature_2m"],
        "cloud_cover_pct": data["hourly"]["cloud_cover"],
        "dni_w_m2": data["hourly"]["direct_normal_irradiance"]
    })
    return df

def generate_synthetic_load_and_solar(df: pd.DataFrame) -> pd.DataFrame:
    """
    Generates synthetic load and solar power based on weather features.
    
    Assumptions (documented):
    - Base load: 3.0 kW
    - Daytime ramp: +2.0 kW during 08:00 - 18:00
    - HVAC dependence: +0.5 kW per degree C above 25C
    - Random equipment events: +0.5 kW noise
    - Load tiers: Critical = 40%, Important = 30%, Flexible = 30%
    
    Solar assumptions:
    - 20kW capacity
    - Linear scaling with DNI, reduced by cloud cover
    """
    # Time features
    hour = df["timestamp"].dt.hour
    
    # Base load + daytime ramp
    base_load = 3.0
    daytime_mask = (hour >= 8) & (hour < 18)
    
    # Temperature dependence (HVAC)
    hvac_load = np.maximum(0, df["temperature_c"] - 25.0) * 0.5
    
    # Noise
    noise = np.random.normal(0, 0.5, size=len(df))
    
    total_load = base_load + np.where(daytime_mask, 2.0, 0.0) + hvac_load + noise
    total_load = np.maximum(0, total_load) # Prevent negative load
    
    df["load_critical_kw"] = total_load * 0.4
    df["load_important_kw"] = total_load * 0.3
    df["load_flexible_kw"] = total_load * 0.3
    
    # Solar generation (kW)
    # DNI typically maxes out around 1000 W/m2. 20kW system -> (DNI / 1000) * 20 * (1 - cloud_cover/100)
    df["solar_kw"] = (df["dni_w_m2"] / 1000.0) * 20.0 * (1.0 - (df["cloud_cover_pct"] / 100.0) * 0.5) # Clouds only block 50% max for simplicity
    df["solar_kw"] = np.maximum(0, df["solar_kw"])
    
    return df

def generate_synthetic_sags(df: pd.DataFrame) -> pd.DataFrame:
    """
    Simulate historical feeder voltage.
    Sri Lankan peak window is 18:30 - 22:30. During this time, high probability of V_pcc < 0.94.
    """
    hour = df["timestamp"].dt.hour
    is_peak = (hour >= 18) & (hour <= 22)
    
    # Background load proxy (sin wave peaking at 20:00)
    bg_proxy = np.sin((hour - 14) * np.pi / 12) * 500.0 
    bg_proxy = np.maximum(0, bg_proxy)
    
    # Add noise
    bg_proxy += np.random.normal(0, 50, size=len(df))
    
    # Voltage calculation (similar to physical/feeder.py)
    # V = 1.0 - Z * bg / 500
    z_pu = 0.1
    v_pcc = 1.0 - z_pu * (bg_proxy / 500.0)
    
    # Random outages (V = 0.0)
    outage_mask = np.random.random(len(df)) < 0.001 # 0.1% chance of outage
    v_pcc[outage_mask] = 0.0
    
    df["v_pcc_pu"] = v_pcc
    return df

if __name__ == "__main__":
    # Generate 1 year of data (2025)
    start_date = "2025-01-01"
    end_date = "2025-12-31"
    
    try:
        df = fetch_weather_open_meteo(start_date, end_date)
    except Exception as e:
        print(f"Failed to fetch Open-Meteo data: {e}")
        print("Generating fully synthetic weather data instead...")
        dates = pd.date_range(start_date, end_date, freq="h", tz="Asia/Colombo")
        df = pd.DataFrame({"timestamp": dates})
        hour = df["timestamp"].dt.hour
        # Synthetic Temp: sine wave 24C night, 32C day
        df["temperature_c"] = 28.0 + 4.0 * np.sin((hour - 9) * np.pi / 12)
        # Synthetic DNI: 0 at night, max 800 at noon
        df["dni_w_m2"] = np.maximum(0, np.sin((hour - 6) * np.pi / 12)) * 800.0
        # Synthetic clouds: random
        df["cloud_cover_pct"] = np.random.randint(0, 100, size=len(df))
        
    df = generate_synthetic_load_and_solar(df)
    df = generate_synthetic_sags(df)
    
    os.makedirs("ml/data", exist_ok=True)
    df.to_csv("ml/data/dataset.csv", index=False)
    print("Dataset generated at ml/data/dataset.csv")
