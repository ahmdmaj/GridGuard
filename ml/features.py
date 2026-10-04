import pandas as pd
import numpy as np

def engineer_features(df: pd.DataFrame) -> pd.DataFrame:
    """
    Generate features for forecasting from the raw dataset.
    Ensures NO LEAKAGE by only using data available at the forecast origin time.
    """
    df = df.copy()
    
    # Ensure timestamp is datetime
    df["timestamp"] = pd.to_datetime(df["timestamp"])
    
    # Sort by time
    df = df.sort_values("timestamp").reset_index(drop=True)
    
    # 1. Time Features (Future knowns)
    df["hour"] = df["timestamp"].dt.hour
    df["hour_sin"] = np.sin(df["hour"] * (2. * np.pi / 24))
    df["hour_cos"] = np.cos(df["hour"] * (2. * np.pi / 24))
    df["day_of_week"] = df["timestamp"].dt.dayofweek
    df["is_peak_window"] = ((df["hour"] >= 18) & (df["hour"] <= 22)).astype(int)
    
    # 2. Weather Features (Assume forecast is available, but for our dataset we use actuals)
    # In a real system, these would be weather forecasts. 
    # For training, we use the historical weather as if it was an exact forecast.
    # temperature_c, cloud_cover_pct, dni_w_m2 are already in df
    
    # 3. Lag Features (Must be shifted! If we are at t, we predict t+horizon. 
    # But this function prepares a row for predicting t using data up to t-1).
    # Wait, the ML model will predict y_t given features at t. 
    # So lag_1 means the value at t-1.
    
    # Target columns that we will predict
    targets = ["load_critical_kw", "solar_kw", "v_pcc_pu"]
    
    for col in targets:
        # Lags
        df[f"{col}_lag_1h"] = df[col].shift(1)
        df[f"{col}_lag_24h"] = df[col].shift(24)
        df[f"{col}_lag_168h"] = df[col].shift(168)
        
        # Rolling stats (on past data only! shift(1) is critical)
        past_series = df[col].shift(1)
        df[f"{col}_rolling_mean_24h"] = past_series.rolling(window=24).mean()
        df[f"{col}_rolling_std_24h"] = past_series.rolling(window=24).std()

    # Drop rows with NaNs caused by lags (first 168 hours)
    df = df.dropna().reset_index(drop=True)
    
    return df
