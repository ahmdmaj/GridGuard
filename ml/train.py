import pandas as pd
import joblib
from sklearn.ensemble import RandomForestRegressor
import os

def train_model(data_path="data/historical_telemetry.csv", model_path="ml/models/forecast_model.joblib"):
    print(f"Loading data from {data_path}...")
    df = pd.read_csv(data_path)
    
    features = ['hour', 'minute', 'day_of_week']
    targets = ['solar_kw', 'critical_kw', 'important_kw', 'flexible_kw']
    
    X = df[features]
    y = df[targets]
    
    print("Training RandomForestRegressor...")
    model = RandomForestRegressor(n_estimators=50, random_state=42)
    model.fit(X, y)
    
    os.makedirs(os.path.dirname(model_path), exist_ok=True)
    joblib.dump(model, model_path)
    print(f"Model saved to {model_path}")

if __name__ == "__main__":
    train_model()
