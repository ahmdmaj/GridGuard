import pandas as pd
import joblib
from sklearn.ensemble import RandomForestRegressor
import os

def train_model(data_path="data/historical_telemetry.csv", model_path="ml/models/forecast_model.joblib"):
    print(f"Loading data from {data_path}...")
    df = pd.read_csv(data_path)
    
    features = ['hour', 'minute', 'day_of_week']
    targets = ['solar_kw', 'critical_kw', 'important_kw', 'flexible_kw']
    
    from sklearn.model_selection import train_test_split
    
    # We want time-based split or just random? The prompt says "split the dataset 80/20". Let's do a time-based split since it's a time series.
    # Actually, random split is fine if we just want to prove it hasn't memorized.
    df_train, df_test = train_test_split(df, test_size=0.2, random_state=42, shuffle=False)
    
    df_test.to_csv("data/test_telemetry.csv", index=False)
    print("Saved data/test_telemetry.csv")
    
    X_train = df_train[features]
    y_train = df_train[targets]
    
    print("Training RandomForestRegressor...")
    model = RandomForestRegressor(n_estimators=50, random_state=42)
    model.fit(X_train, y_train)
    
    os.makedirs(os.path.dirname(model_path), exist_ok=True)
    joblib.dump(model, model_path)
    print(f"Model saved to {model_path}")

if __name__ == "__main__":
    train_model()
