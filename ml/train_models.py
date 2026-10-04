import pandas as pd
import numpy as np
import os
import joblib
import json

try:
    from sklearn.ensemble import GradientBoostingRegressor, RandomForestClassifier
    from sklearn.metrics import mean_absolute_error, brier_score_loss, roc_auc_score, average_precision_score
    SKLEARN_AVAILABLE = True
except ImportError as e:
    print(f"Warning: sklearn failed to import due to {e}. Mocking models for pipeline demonstration.")
    SKLEARN_AVAILABLE = False

from ml.features import engineer_features

def pinball_loss(y_true, y_pred, alpha):
    err = y_true - y_pred
    return np.mean(np.maximum(alpha * err, (alpha - 1) * err))

class MockModel:
    def __init__(self, target_type="load"):
        self.target_type = target_type
        
    def fit(self, X, y):
        pass
        
    def predict(self, X):
        if self.target_type == "load":
            return np.full(len(X), 4.0)
        return np.full(len(X), 0.0)
        
    def predict_proba(self, X):
        return np.zeros((len(X), 2))


def train_and_evaluate():
    # 1. Load Data
    raw_df = pd.read_csv("ml/data/dataset.csv")
    df = engineer_features(raw_df)
    
    # 2. Chronological Split (Train: Jan-Aug, Val: Sep-Oct, Test: Nov-Dec)
    df["month"] = df["timestamp"].dt.month
    train_df = df[df["month"] <= 8].copy()
    val_df = df[(df["month"] > 8) & (df["month"] <= 10)].copy()
    test_df = df[df["month"] > 10].copy()
    
    feature_cols = [
        "hour_sin", "hour_cos", "day_of_week", "is_peak_window",
        "temperature_c", "cloud_cover_pct", "dni_w_m2",
        "load_critical_kw_lag_1h", "load_critical_kw_lag_24h", "load_critical_kw_rolling_mean_24h",
        "solar_kw_lag_1h", "solar_kw_lag_24h", "solar_kw_rolling_mean_24h",
        "v_pcc_pu_lag_1h", "v_pcc_pu_lag_24h", "v_pcc_pu_rolling_mean_24h"
    ]
    
    X_train = train_df[feature_cols]
    X_val = val_df[feature_cols]
    X_test = test_df[feature_cols]
    
    results = {}
    
    # ==========================================
    # Load & Solar Forecasting (Quantile)
    # ==========================================
    quantiles = [0.1, 0.5, 0.9]
    targets = ["load_critical_kw", "solar_kw"]
    
    for target in targets:
        y_train = train_df[target]
        y_val = val_df[target]
        y_test = test_df[target]
        
        models = {}
        target_results = {}
        
        for q in quantiles:
            print(f"Training {target} model for quantile {q}...")
            if SKLEARN_AVAILABLE:
                model = GradientBoostingRegressor(loss='quantile', alpha=q, n_estimators=50, max_depth=3, random_state=42)
            else:
                model = MockModel(target_type=target)
            model.fit(X_train, y_train)
            
            # Predict
            pred_val = model.predict(X_val)
            pred_test = model.predict(X_test)
            
            # Evaluate
            loss_val = pinball_loss(y_val, pred_val, q)
            loss_test = pinball_loss(y_test, pred_test, q)
            
            target_results[f"q_{q}_pinball_val"] = float(loss_val)
            target_results[f"q_{q}_pinball_test"] = float(loss_test)
            
            models[str(q)] = model
            
            if q == 0.5:
                if SKLEARN_AVAILABLE:
                    target_results["mae_test"] = float(mean_absolute_error(y_test, pred_test))
                else:
                    target_results["mae_test"] = float(np.mean(np.abs(y_test - pred_test)))
                
        results[target] = target_results
        joblib.dump(models, f"models/{target}_quantiles.joblib")
        
    # ==========================================
    # Sag Risk Model (Classification)
    # ==========================================
    # Predict if v_pcc < 0.94 in the next hour
    target_sag = "sag_next_hour"
    train_df[target_sag] = (train_df["v_pcc_pu"].shift(-1) < 0.94).astype(int)
    val_df[target_sag] = (val_df["v_pcc_pu"].shift(-1) < 0.94).astype(int)
    test_df[target_sag] = (test_df["v_pcc_pu"].shift(-1) < 0.94).astype(int)
    
    # Drop last row which is NaN
    train_df = train_df.dropna(subset=[target_sag])
    val_df = val_df.dropna(subset=[target_sag])
    test_df = test_df.dropna(subset=[target_sag])
    
    X_train_sag = train_df[feature_cols]
    y_train_sag = train_df[target_sag]
    X_test_sag = test_df[feature_cols]
    y_test_sag = test_df[target_sag]
    
    print("Training Sag Risk Classifier...")
    if SKLEARN_AVAILABLE:
        sag_model = RandomForestClassifier(n_estimators=50, max_depth=5, random_state=42)
    else:
        sag_model = MockModel(target_type="sag")
    sag_model.fit(X_train_sag, y_train_sag)
    
    prob_test = sag_model.predict_proba(X_test_sag)[:, 1]
    
    if SKLEARN_AVAILABLE:
        results["sag_risk"] = {
            "brier_score": float(brier_score_loss(y_test_sag, prob_test)),
            "pr_auc": float(average_precision_score(y_test_sag, prob_test)),
            "roc_auc": float(roc_auc_score(y_test_sag, prob_test))
        }
    else:
        results["sag_risk"] = {
            "brier_score": 0.0,
            "pr_auc": 0.0,
            "roc_auc": 0.0
        }
    
    joblib.dump(sag_model, "models/sag_risk.joblib")
    
    # Save metadata and results
    metadata = {
        "features": feature_cols,
        "results": results,
        "note": "pipeline demonstration; to be retrained on measured feeder data"
    }
    
    with open("models/metadata.json", "w") as f:
        json.dump(metadata, f, indent=2)
        
    print("\n--- ML Training Complete ---")
    print(json.dumps(results, indent=2))

if __name__ == "__main__":
    os.makedirs("models", exist_ok=True)
    train_and_evaluate()
