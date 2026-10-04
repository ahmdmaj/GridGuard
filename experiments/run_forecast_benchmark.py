import pandas as pd
import numpy as np
import datetime
import os
import sys

# Ensure the root project directory is in the Python path
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))
from sklearn.metrics import mean_absolute_error, mean_squared_error
import joblib

from digital_twin.state import DigitalTwinState, GridState, SolarState, BatteryState, GeneratorState, LoadState
from forecasting.service import PersistenceForecastService, MLForecastService
from controller.engine import DecisionEngine
from metrics.esh import ESHCalculator

class HourlyMeanForecastService:
    def __init__(self, means_df):
        self.means = means_df
        
    def generate_forecast(self, twin_state: DigitalTwinState, steps_ahead: int) -> list[dict]:
        timestamp_str = twin_state.timestamp
        if timestamp_str.endswith("Z"):
            timestamp_str = timestamp_str[:-1]
        try:
            current_dt = datetime.datetime.fromisoformat(timestamp_str)
        except ValueError:
            current_dt = datetime.datetime(2026, 1, 1, 0, 0, 0)
            
        forecasts = []
        for i in range(1, steps_ahead + 1):
            future_dt = current_dt + datetime.timedelta(minutes=5 * i)
            h = future_dt.hour
            # Get mean for hour h
            row = self.means[self.means['hour'] == h].iloc[0]
            forecasts.append({
                "solar_kw": max(0.0, float(row['solar_kw'])),
                "load_critical_kw": max(0.0, float(row['critical_kw'])),
                "load_important_kw": max(0.0, float(row['important_kw'])),
                "load_flexible_kw": max(0.0, float(row['flexible_kw']))
            })
        return forecasts

def format_table(df, title):
    print("\n" + "="*80)
    print(title.center(80))
    print("="*80)
    print(df.to_string(index=False))
    print("="*80)

def part_a_accuracy_metrics():
    print("Loading test dataset...")
    df_test = pd.read_csv("data/test_telemetry.csv")
    df_train = pd.read_csv("data/historical_telemetry.csv")
    
    # Exclude the test part from train for strict isolation
    df_train = df_train.head(len(df_train) - len(df_test))
    
    # True values
    y_true_solar = df_test['solar_kw'].values
    y_true_demand = (df_test['critical_kw'] + df_test['important_kw'] + df_test['flexible_kw']).values
    
    # 1. Persistence (Shift by 1)
    y_pred_solar_pers = df_test['solar_kw'].shift(1).fillna(0).values
    y_pred_demand_pers = (df_test['critical_kw'] + df_test['important_kw'] + df_test['flexible_kw']).shift(1).fillna(0).values
    
    # 2. Rule-Based (Hourly Means)
    hourly_means = df_train.groupby('hour')[['solar_kw', 'critical_kw', 'important_kw', 'flexible_kw']].mean().reset_index()
    df_test_rule = df_test.merge(hourly_means, on='hour', suffixes=('', '_mean'))
    y_pred_solar_rule = df_test_rule['solar_kw_mean'].values
    y_pred_demand_rule = (df_test_rule['critical_kw_mean'] + df_test_rule['important_kw_mean'] + df_test_rule['flexible_kw_mean']).values
    
    # 3. ML Forecast (Random Forest)
    model = joblib.load("ml/models/forecast_model.joblib")
    features = ['hour', 'minute', 'day_of_week']
    ml_preds = model.predict(df_test[features])
    
    y_pred_solar_ml = ml_preds[:, 0]
    y_pred_demand_ml = ml_preds[:, 1] + ml_preds[:, 2] + ml_preds[:, 3]
    
    results = []
    
    for name, pred_solar, pred_demand in [
        ("Persistence", y_pred_solar_pers, y_pred_demand_pers),
        ("Rule-Based (Hourly Mean)", y_pred_solar_rule, y_pred_demand_rule),
        ("Random Forest (ML)", y_pred_solar_ml, y_pred_demand_ml)
    ]:
        results.append({
            "Model": name,
            "Solar MAE (kW)": round(mean_absolute_error(y_true_solar, pred_solar), 3),
            "Solar RMSE (kW)": round(np.sqrt(mean_squared_error(y_true_solar, pred_solar)), 3),
            "Demand MAE (kW)": round(mean_absolute_error(y_true_demand, pred_demand), 3),
            "Demand RMSE (kW)": round(np.sqrt(mean_squared_error(y_true_demand, pred_demand)), 3),
        })
        
    df_results = pd.DataFrame(results)
    
    os.makedirs("results", exist_ok=True)
    df_results.to_csv("results/ml_benchmark_metrics.csv", index=False)
    
    format_table(df_results, "FORECASTING BENCHMARK (UNSEEN DATA)")
    return hourly_means

def part_b_decision_impact(hourly_means):
    # Setup Targeted Simulation State
    # Grid OFF, Battery 30% SOC, Solar 5.0, Demand 6.0 (3, 2, 1)
    # Time: 17:00 (Sunset approaching)
    twin_state = DigitalTwinState(
        timestamp="2026-01-01T17:00:00Z",
        grid=GridState(voltage_pu=0.0, is_available=False),
        solar=SolarState(power_kw=5.0),
        battery=BatteryState(soc=30.0),
        generator=GeneratorState(fuel_liters=0.0, is_available=False, power_kw=0.0),
        loads=LoadState(critical_kw=3.0, important_kw=2.0, flexible_kw=1.0)
    )
    
    config = {
        "battery_capacity_kwh": 40.0,
        "generator_capacity_kw": 15.0,
        "esh_threshold_hours": 24.0, # Just using default/standard logic inside Engine
        "generator_start_esh_hours": 4.0,
        "shed_flexible_esh": 6.0,
    }
    
    esh_calc = ESHCalculator(config)
    
    services = {
        "Persistence": PersistenceForecastService(),
        "Rule-Based": HourlyMeanForecastService(hourly_means),
        "Random Forest (ML)": MLForecastService()
    }
    
    results = []
    
    for name, service in services.items():
        engine = DecisionEngine(config)
        # Evaluate
        forecasts = service.generate_forecast(twin_state, 12*12) # 12 hours ahead
        expected_esh = esh_calc.calculate_forecast_esh(twin_state, forecasts, assume_island=False)
        shadow_esh = esh_calc.calculate_forecast_esh(twin_state, forecasts, assume_island=True)
        
        cmd = engine.evaluate(twin_state, expected_esh, shadow_esh)
        
        results.append({
            "Forecast Type": name,
            "Battery SOC": "30%",
            "Grid": "OFF",
            "Calc ESH (hrs)": round(shadow_esh.get("all_loads_hours", 0), 2),
            "Gen Run Cmd": cmd.get("generator_run", False),
            "Shed Flexible": not cmd.get("connect_flexible", True),
            "Decision Reason": cmd.get("decision_reason", "")
        })
        
    df_results = pd.DataFrame(results)
    df_results.to_csv("results/ml_decision_impact.csv", index=False)
    
    format_table(df_results, "DECISION ENGINE IMPACT: FORECAST DEPENDENCE (17:00 SUNSET)")

if __name__ == "__main__":
    hourly_means = part_a_accuracy_metrics()
    part_b_decision_impact(hourly_means)
