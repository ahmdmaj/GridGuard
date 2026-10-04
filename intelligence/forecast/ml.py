import datetime
import numpy as np
import pandas as pd
import joblib
import os
from intelligence.forecast.base import ForecastBundle, ForecastService
from intelligence.forecast.rule import RuleForecastService

class MLForecastService(ForecastService):
    def __init__(self, model_dir: str = "models"):
        self.model_dir = model_dir
        self.fallback = RuleForecastService()
        self.models_loaded = False
        self._load_models()
        
    def _load_models(self):
        try:
            self.load_models = joblib.load(os.path.join(self.model_dir, "load_critical_kw_quantiles.joblib"))
            self.solar_models = joblib.load(os.path.join(self.model_dir, "solar_kw_quantiles.joblib"))
            self.sag_model = joblib.load(os.path.join(self.model_dir, "sag_risk.joblib"))
            self.models_loaded = True
        except Exception as e:
            print(f"MLForecastService fallback: {e}")
            self.models_loaded = False
            
    def _extract_features(self, telemetry_history: list, now: datetime.datetime, horizon_steps: int, step_s: int) -> pd.DataFrame:
        # In a real system, we'd process telemetry_history into the feature format.
        # For this prototype, we'll generate synthetic features matching the model expectations.
        features = []
        for i in range(horizon_steps):
            t = now + datetime.timedelta(seconds=i*step_s)
            
            # Use last telemetry for lags if available
            last_load = telemetry_history[-1].get("load_critical_kw", 4.0) if telemetry_history else 4.0
            last_solar = telemetry_history[-1].get("solar_kw", 0.0) if telemetry_history else 0.0
            last_v = telemetry_history[-1].get("v_rms_pu", 1.0) if telemetry_history else 1.0
            
            feat = {
                "hour_sin": np.sin(t.hour * (2. * np.pi / 24)),
                "hour_cos": np.cos(t.hour * (2. * np.pi / 24)),
                "day_of_week": t.dayofweek,
                "is_peak_window": 1 if 18 <= t.hour <= 22 else 0,
                "temperature_c": 30.0, # Dummy forecast
                "cloud_cover_pct": 50.0,
                "dni_w_m2": 500.0 if 8 <= t.hour <= 16 else 0.0,
                "load_critical_kw_lag_1h": last_load,
                "load_critical_kw_lag_24h": last_load,
                "load_critical_kw_rolling_mean_24h": last_load,
                "solar_kw_lag_1h": last_solar,
                "solar_kw_lag_24h": last_solar,
                "solar_kw_rolling_mean_24h": last_solar,
                "v_pcc_pu_lag_1h": last_v,
                "v_pcc_pu_lag_24h": last_v,
                "v_pcc_pu_rolling_mean_24h": last_v
            }
            features.append(feat)
        return pd.DataFrame(features)

    def forecast(self, telemetry_history: list, now: datetime.datetime, horizon_s: int) -> ForecastBundle:
        step_s = 3600 # Models are trained on hourly data
        steps = int(horizon_s / step_s)
        
        if not self.models_loaded or steps == 0:
            return self.fallback.forecast(telemetry_history, now, horizon_s)
            
        features_df = self._extract_features(telemetry_history, now, steps, step_s)
        
        # Predict
        try:
            load_kw = {
                "p10": self.load_models["0.1"].predict(features_df),
                "p50": self.load_models["0.5"].predict(features_df),
                "p90": self.load_models["0.9"].predict(features_df)
            }
            
            solar_kw = {
                "p10": np.maximum(0, self.solar_models["0.1"].predict(features_df)),
                "p50": np.maximum(0, self.solar_models["0.5"].predict(features_df)),
                "p90": np.maximum(0, self.solar_models["0.9"].predict(features_df))
            }
            
            sag_prob = self.sag_model.predict_proba(features_df)[:, 1]
            grid_ok_prob = 1.0 - sag_prob
            
            return ForecastBundle(
                t0=now,
                step_s=step_s,
                load_kw=load_kw,
                solar_kw=solar_kw,
                grid_ok_prob=grid_ok_prob,
                confidence=0.9,
                source="ml"
            )
        except Exception as e:
            print(f"MLForecastService prediction failed: {e}")
            return self.fallback.forecast(telemetry_history, now, horizon_s)
