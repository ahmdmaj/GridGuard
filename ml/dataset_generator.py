import pandas as pd
import numpy as np
import datetime
import os

def generate_dataset(output_path="data/historical_telemetry.csv"):
    np.random.seed(42)
    start_time = datetime.datetime(2025, 1, 1, 0, 0, 0)
    steps = 30 * 24 * 60 // 5  # 30 days of 5-minute intervals (8640)
    
    times = [start_time + datetime.timedelta(minutes=5*i) for i in range(steps)]
    hours = [t.hour for t in times]
    minutes = [t.minute for t in times]
    days_of_week = [t.weekday() for t in times]
    
    # Solar: sine wave peaking at noon, 0 at night
    # hour=12 is peak, from 6 to 18
    solar_kw = []
    for h, m in zip(hours, minutes):
        time_hours = h + m / 60.0
        if 6 <= time_hours <= 18:
            # normalized 0 to 1 over the 12 hours
            val = np.sin((time_hours - 6) / 12 * np.pi) * 10.0
        else:
            val = 0.0
        # Add noise
        val += np.random.normal(0, 0.5)
        solar_kw.append(max(0, val))
        
    # Loads
    critical_kw = [max(0, 4.0 + np.random.normal(0, 0.2)) for _ in range(steps)]
    important_kw = []
    flexible_kw = []
    
    for h in hours:
        # diurnal peaks
        if 7 <= h <= 9 or 18 <= h <= 21:
            important_kw.append(max(0, 3.5 + np.random.normal(0, 0.3)))
            flexible_kw.append(max(0, 2.5 + np.random.normal(0, 0.3)))
        else:
            important_kw.append(max(0, 3.0 + np.random.normal(0, 0.2)))
            flexible_kw.append(max(0, 2.0 + np.random.normal(0, 0.2)))
            
    df = pd.DataFrame({
        "timestamp": times,
        "hour": hours,
        "minute": minutes,
        "day_of_week": days_of_week,
        "solar_kw": solar_kw,
        "critical_kw": critical_kw,
        "important_kw": important_kw,
        "flexible_kw": flexible_kw
    })
    
    os.makedirs(os.path.dirname(output_path), exist_ok=True)
    df.to_csv(output_path, index=False)
    print(f"Dataset generated with {len(df)} rows at {output_path}")

if __name__ == "__main__":
    generate_dataset()
