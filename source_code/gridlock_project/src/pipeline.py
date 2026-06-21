"""
BengaluruAI Traffic Intelligence — Event-Driven Congestion Forecaster
Feature engineering + dual ML model pipeline
"""

import pandas as pd
import numpy as np
import json
import pickle
import os
from datetime import timedelta

# ─── 1. DATA LOADING & CLEANING ─────────────────────────────────────────────

def load_and_clean(path: str) -> pd.DataFrame:
    df = pd.read_csv(path)

    # Parse datetimes (UTC)
    for col in ['start_datetime', 'closed_datetime', 'resolved_datetime']:
        df[col] = pd.to_datetime(df[col], utc=True, errors='coerce')

    # IST = UTC + 5h30m
    IST = timedelta(hours=5, minutes=30)
    df['start_IST'] = df['start_datetime'] + IST

    # Compute actual duration (prefer closed over resolved)
    end_time = df['closed_datetime'].fillna(df['resolved_datetime'])
    df['duration_mins'] = (end_time - df['start_datetime']).dt.total_seconds() / 60

    # Drop negatives / clearly corrupt rows
    df = df[df['duration_mins'].isna() | (df['duration_mins'] > 0)].copy()

    # Normalise event_cause casing
    df['event_cause'] = df['event_cause'].str.strip().str.lower().replace({'debris': 'Debris'.lower()})

    return df


# ─── 2. FEATURE ENGINEERING ─────────────────────────────────────────────────

# Historical stats computed from training data (populated in build_features)
_CAUSE_STATS = {}
_CORRIDOR_STATS = {}
_JUNCTION_STATS = {}
_ZONE_STATS = {}

def _compute_lookup_tables(df: pd.DataFrame):
    """Compute per-category aggregate stats for target encoding."""
    global _CAUSE_STATS, _CORRIDOR_STATS, _JUNCTION_STATS, _ZONE_STATS

    has_dur = df['duration_mins'].notna()

    # --- Cause stats ---
    cause = df.groupby('event_cause').agg(
        closure_rate=('requires_road_closure', 'mean'),
        median_duration=('duration_mins', lambda x: x.dropna().median()),
        event_count=('id', 'count'),
    ).reset_index()
    # Severity score: weighted composite
    cause['severity_score'] = (
        0.5 * cause['closure_rate'] +
        0.3 * (cause['median_duration'].clip(0, 10000) / 10000) +
        0.2 * (cause['event_count'] / cause['event_count'].max())
    )
    _CAUSE_STATS = cause.set_index('event_cause').to_dict('index')

    # --- Corridor stats ---
    corr = df.groupby('corridor').agg(
        event_count=('id', 'count'),
        closure_rate=('requires_road_closure', 'mean'),
        high_priority_rate=('priority', lambda x: (x == 'High').mean()),
    ).reset_index()
    corr['corridor_risk'] = (
        0.4 * corr['closure_rate'] +
        0.4 * corr['high_priority_rate'] +
        0.2 * (corr['event_count'] / corr['event_count'].max())
    )
    _CORRIDOR_STATS = corr.set_index('corridor').to_dict('index')

    # --- Junction stats ---
    junc = df[df['junction'].notna()].groupby('junction').agg(
        event_count=('id', 'count'),
        closure_rate=('requires_road_closure', 'mean'),
    ).reset_index()
    junc['junction_risk'] = (
        0.5 * junc['closure_rate'] +
        0.5 * (junc['event_count'] / junc['event_count'].max())
    )
    _JUNCTION_STATS = junc.set_index('junction').to_dict('index')

    # --- Zone stats ---
    zone = df[df['zone'].notna()].groupby('zone').agg(
        event_count=('id', 'count'),
        closure_rate=('requires_road_closure', 'mean'),
    ).reset_index()
    zone['zone_density'] = zone['event_count'] / zone['event_count'].max()
    _ZONE_STATS = zone.set_index('zone').to_dict('index')


def build_features(df: pd.DataFrame, fit: bool = False) -> pd.DataFrame:
    """Build the full feature matrix from raw DataFrame."""
    if fit:
        _compute_lookup_tables(df)

    feat = pd.DataFrame(index=df.index)

    # ── Temporal ──────────────────────────────────────────────────────
    feat['hour_IST'] = df['start_IST'].dt.hour.fillna(12)
    feat['minute_IST'] = df['start_IST'].dt.minute.fillna(0)
    feat['day_of_week'] = df['start_IST'].dt.dayofweek.fillna(2)
    feat['month'] = df['start_IST'].dt.month.fillna(1)
    feat['day_of_month'] = df['start_IST'].dt.day.fillna(15)
    feat['is_weekend'] = (feat['day_of_week'] >= 5).astype(int)
    feat['is_peak_morning'] = ((feat['hour_IST'] >= 8) & (feat['hour_IST'] <= 11)).astype(int)
    feat['is_peak_evening'] = ((feat['hour_IST'] >= 17) & (feat['hour_IST'] <= 21)).astype(int)
    feat['is_peak'] = ((feat['is_peak_morning'] == 1) | (feat['is_peak_evening'] == 1)).astype(int)
    feat['is_night'] = ((feat['hour_IST'] >= 22) | (feat['hour_IST'] <= 5)).astype(int)

    # ── Event type & cause ────────────────────────────────────────────
    feat['is_planned'] = (df['event_type'] == 'planned').astype(int)
    feat['priority_high'] = (df['priority'] == 'High').astype(int)

    # Target-encode cause
    feat['cause_closure_rate'] = df['event_cause'].map(
        lambda c: _CAUSE_STATS.get(c, {}).get('closure_rate', 0.05))
    feat['cause_median_duration'] = df['event_cause'].map(
        lambda c: np.log1p(_CAUSE_STATS.get(c, {}).get('median_duration', 60) or 60))
    feat['cause_severity_score'] = df['event_cause'].map(
        lambda c: _CAUSE_STATS.get(c, {}).get('severity_score', 0.1))
    feat['cause_event_count'] = df['event_cause'].map(
        lambda c: _CAUSE_STATS.get(c, {}).get('event_count', 10))

    # Ordinal cause encoding for high-impact categories
    CAUSE_ORD = {
        'vip_movement': 9, 'public_event': 8, 'protest': 7, 'procession': 6,
        'construction': 5, 'tree_fall': 4, 'water_logging': 3,
        'accident': 3, 'road_conditions': 2, 'vehicle_breakdown': 1,
        'pot_holes': 1, 'congestion': 2, 'others': 1,
        'fog / low visibility': 2, 'debris': 2,
    }
    feat['cause_ordinal'] = df['event_cause'].str.lower().map(CAUSE_ORD).fillna(1).astype(int)

    # Vehicle type encoding
    VEH_ORD = {
        'heavy_vehicle': 5, 'truck': 5, 'bmtc_bus': 4, 'ksrtc_bus': 4,
        'private_bus': 3, 'lcv': 2, 'private_car': 2, 'taxi': 1, 'auto': 1,
    }
    feat['veh_type_encoded'] = df['veh_type'].str.lower().map(VEH_ORD).fillna(0)
    feat['has_vehicle'] = df['veh_type'].notna().astype(int)

    # ── Spatial ───────────────────────────────────────────────────────
    feat['latitude'] = df['latitude'].fillna(df['latitude'].median())
    feat['longitude'] = df['longitude'].fillna(df['longitude'].median())

    feat['corridor_risk'] = df['corridor'].map(
        lambda c: _CORRIDOR_STATS.get(c, {}).get('corridor_risk', 0.1))
    feat['corridor_event_count'] = df['corridor'].map(
        lambda c: _CORRIDOR_STATS.get(c, {}).get('event_count', 5))
    feat['corridor_closure_rate'] = df['corridor'].map(
        lambda c: _CORRIDOR_STATS.get(c, {}).get('closure_rate', 0.05))

    feat['junction_risk'] = df['junction'].map(
        lambda j: _JUNCTION_STATS.get(j, {}).get('junction_risk', 0.0) if pd.notna(j) else 0.0)
    feat['has_junction'] = df['junction'].notna().astype(int)

    feat['zone_density'] = df['zone'].map(
        lambda z: _ZONE_STATS.get(z, {}).get('zone_density', 0.0) if pd.notna(z) else 0.0)
    feat['has_zone'] = df['zone'].notna().astype(int)

    # Distance from city centre (Majestic / KR Circle)
    CITY_LAT, CITY_LON = 12.9766, 77.5713
    feat['dist_from_centre'] = np.sqrt(
        (feat['latitude'] - CITY_LAT)**2 + (feat['longitude'] - CITY_LON)**2
    ) * 111  # rough km

    # ── Composite interaction features ───────────────────────────────
    feat['impact_index'] = (
        0.35 * feat['cause_closure_rate'] +
        0.25 * feat['corridor_risk'] +
        0.20 * feat['is_peak'].astype(float) +
        0.20 * feat['priority_high'].astype(float)
    )
    feat['peak_x_severity'] = feat['is_peak'] * feat['cause_severity_score']
    feat['planned_x_cause'] = feat['is_planned'] * feat['cause_ordinal']

    return feat


# ─── 3. MODEL TRAINING ──────────────────────────────────────────────────────

def train_models(df: pd.DataFrame):
    import lightgbm as lgb
    from sklearn.model_selection import train_test_split
    from sklearn.metrics import (f1_score, roc_auc_score,
                                  mean_squared_error, r2_score)

    X = build_features(df, fit=True)
    FEATURES = X.columns.tolist()

    # ── Model A: Road closure classifier ─────────────────────────────
    y_cls = df['requires_road_closure'].astype(int)
    X_tr, X_te, y_tr, y_te = train_test_split(
        X, y_cls, test_size=0.2, random_state=42, stratify=y_cls)

    pos_weight = (y_tr == 0).sum() / (y_tr == 1).sum()

    clf = lgb.LGBMClassifier(
        n_estimators=400,
        learning_rate=0.05,
        max_depth=6,
        num_leaves=40,
        min_child_samples=20,
        scale_pos_weight=pos_weight,
        subsample=0.8,
        colsample_bytree=0.8,
        random_state=42,
        verbose=-1,
    )
    clf.fit(X_tr, y_tr,
            eval_set=[(X_te, y_te)],
            callbacks=[lgb.early_stopping(30, verbose=False),
                       lgb.log_evaluation(-1)])

    y_pred_cls = clf.predict(X_te)
    y_prob_cls = clf.predict_proba(X_te)[:, 1]
    print(f"[Classifier] F1={f1_score(y_te, y_pred_cls):.3f}  AUC={roc_auc_score(y_te, y_prob_cls):.3f}")

    # ── Model B: Duration regressor ──────────────────────────────────
    dur_mask = df['duration_mins'].notna() & (df['duration_mins'] > 0)
    X_dur = X[dur_mask]
    y_reg = np.log1p(df.loc[dur_mask, 'duration_mins'])

    X_tr2, X_te2, y_tr2, y_te2 = train_test_split(
        X_dur, y_reg, test_size=0.2, random_state=42)

    import xgboost as xgb
    reg = xgb.XGBRegressor(
        n_estimators=500,
        learning_rate=0.04,
        max_depth=6,
        subsample=0.8,
        colsample_bytree=0.8,
        min_child_weight=5,
        random_state=42,
        verbosity=0,
        early_stopping_rounds=30,
    )
    reg.fit(X_tr2, y_tr2,
            eval_set=[(X_te2, y_te2)],
            verbose=False)

    y_pred_reg = reg.predict(X_te2)
    rmse = np.sqrt(mean_squared_error(y_te2, y_pred_reg))
    r2 = r2_score(y_te2, y_pred_reg)
    # Median absolute error in actual minutes
    mae_mins = np.median(np.abs(np.expm1(y_te2) - np.expm1(y_pred_reg)))
    print(f"[Regressor] RMSE(log)={rmse:.3f}  R²={r2:.3f}  MedianAE={mae_mins:.1f} mins")

    # Feature importance (classifier)
    fi = pd.Series(clf.feature_importances_, index=FEATURES).sort_values(ascending=False)
    print("\n[Top-10 features by importance]")
    print(fi.head(10))

    return clf, reg, FEATURES


# ─── 4. RECOMMENDATION ENGINE ───────────────────────────────────────────────

def recommend(
    closure_prob: float,
    predicted_duration_mins: float,
    cause: str,
    corridor: str,
    is_peak: bool,
    severity_score: float,
) -> dict:
    """
    Rule-based recommendation layer on top of ML output.
    Returns manpower, barricade count, alert tier, diversion flag.
    """
    # Alert tier
    impact = (
        0.40 * closure_prob +
        0.30 * min(predicted_duration_mins / 480, 1.0) +  # cap at 8h
        0.20 * severity_score +
        0.10 * float(is_peak)
    )
    if impact >= 0.65:
        tier = "CRITICAL"
    elif impact >= 0.40:
        tier = "HIGH"
    elif impact >= 0.20:
        tier = "MEDIUM"
    else:
        tier = "LOW"

    # Manpower
    base_officers = {'CRITICAL': 6, 'HIGH': 4, 'MEDIUM': 2, 'LOW': 1}[tier]
    officers = base_officers + (2 if is_peak else 0) + (1 if closure_prob > 0.7 else 0)

    # Barricades
    barricades = {'CRITICAL': 4, 'HIGH': 2, 'MEDIUM': 1, 'LOW': 0}[tier]
    if closure_prob > 0.5:
        barricades += 1

    # Diversion recommendation
    HIGH_RISK_CORRIDORS = {'Mysore Road', 'Bellary Road 1', 'Bellary Road 2',
                            'Hosur Road', 'Tumkur Road', 'ORR North 1', 'ORR East 1'}
    needs_diversion = (closure_prob > 0.4 and corridor in HIGH_RISK_CORRIDORS) or tier == 'CRITICAL'

    # Response time target (minutes)
    response_time = {'CRITICAL': 10, 'HIGH': 20, 'MEDIUM': 30, 'LOW': 60}[tier]

    return {
        'alert_tier': tier,
        'impact_index': round(impact, 3),
        'closure_probability_pct': round(closure_prob * 100, 1),
        'predicted_duration_mins': round(predicted_duration_mins),
        'predicted_duration_hrs': round(predicted_duration_mins / 60, 1),
        'officers_recommended': officers,
        'barricades_recommended': barricades,
        'activate_diversion': needs_diversion,
        'target_response_mins': response_time,
    }


# ─── 5. POST-EVENT LEARNING ──────────────────────────────────────────────────

class PostEventLearner:
    """
    Tracks predicted vs actual outcomes.
    Updates a correction factor table per (cause, hour_bucket, corridor).
    """
    def __init__(self):
        self.records = []
        self.corrections = {}  # key → mean_error_mins

    def log(self, event_id, cause, corridor, hour_IST,
            predicted_mins, actual_mins, predicted_closure, actual_closure):
        bucket = f"{cause}|{corridor}|{'peak' if 6 <= hour_IST <= 22 else 'off'}"
        error = actual_mins - predicted_mins if actual_mins else None
        record = dict(
            event_id=event_id, cause=cause, corridor=corridor, hour_IST=hour_IST,
            predicted_mins=predicted_mins, actual_mins=actual_mins,
            error_mins=error,
            predicted_closure=predicted_closure, actual_closure=actual_closure,
            closure_correct=predicted_closure == actual_closure,
            bucket=bucket,
        )
        self.records.append(record)
        if error is not None:
            prev = self.corrections.get(bucket, [])
            prev.append(error)
            self.corrections[bucket] = prev

    def correction_factor(self, cause, corridor, hour_IST):
        bucket = f"{cause}|{corridor}|{'peak' if 6 <= hour_IST <= 22 else 'off'}"
        errors = self.corrections.get(bucket, [])
        return np.mean(errors) if errors else 0.0

    def summary(self):
        if not self.records:
            return {}
        df = pd.DataFrame(self.records)
        return {
            'total_logged': len(df),
            'closure_accuracy': df['closure_correct'].mean(),
            'mean_duration_error_mins': df['error_mins'].dropna().mean(),
            'median_duration_error_mins': df['error_mins'].dropna().median(),
        }


# ─── 6. INFERENCE ────────────────────────────────────────────────────────────

def predict_event(clf, reg, features: list, learner: PostEventLearner,
                   event_cause: str, corridor: str, event_type: str,
                   start_datetime_IST, latitude: float, longitude: float,
                   priority: str = 'High', junction: str = None,
                   zone: str = None, veh_type: str = None) -> dict:
    """Single-event inference endpoint used by the dashboard."""

    import pandas as pd

    row = pd.DataFrame([{
        'event_type': event_type,
        'event_cause': event_cause,
        'corridor': corridor,
        'priority': priority,
        'junction': junction,
        'zone': zone,
        'veh_type': veh_type,
        'latitude': latitude,
        'longitude': longitude,
        'start_IST': pd.Timestamp(start_datetime_IST),
        'duration_mins': None,
        'id': 'LIVE',
        'requires_road_closure': False,
    }])

    X = build_features(row, fit=False)[features]

    closure_prob = clf.predict_proba(X)[0, 1]
    log_dur = reg.predict(X)[0]
    duration_mins = float(np.expm1(log_dur))

    # Apply learner correction
    hour_IST = pd.Timestamp(start_datetime_IST).hour
    correction = learner.correction_factor(event_cause, corridor, hour_IST)
    duration_mins = max(0, duration_mins + correction)

    cause_stats = _CAUSE_STATS.get(event_cause, {})
    severity = cause_stats.get('severity_score', 0.1)
    is_peak = 8 <= hour_IST <= 11 or 17 <= hour_IST <= 21

    rec = recommend(closure_prob, duration_mins, event_cause, corridor, is_peak, severity)

    # Historical context for this cause
    historical = {
        'cause_median_duration_mins': round(cause_stats.get('median_duration', 0) or 0),
        'cause_closure_rate_pct': round((cause_stats.get('closure_rate', 0) or 0) * 100, 1),
        'corridor_risk_score': round((_CORRIDOR_STATS.get(corridor, {}).get('corridor_risk', 0) or 0), 3),
    }

    return {**rec, 'historical': historical, 'correction_applied_mins': round(correction, 1)}


# ─── 7. TRAIN & SAVE ─────────────────────────────────────────────────────────

if __name__ == '__main__':
    DATA_PATH = os.path.join(os.path.dirname(__file__), '..', 'data', 'events.csv')
    MODEL_DIR = os.path.join(os.path.dirname(__file__), '..', 'models')

    print("Loading data...")
    df = load_and_clean(DATA_PATH)
    print(f"  {len(df)} events loaded")

    print("\nTraining models...")
    clf, reg, features = train_models(df)

    print("\nSaving models & lookup tables...")
    with open(os.path.join(MODEL_DIR, 'classifier.pkl'), 'wb') as f:
        pickle.dump(clf, f)
    with open(os.path.join(MODEL_DIR, 'regressor.pkl'), 'wb') as f:
        pickle.dump(reg, f)
    with open(os.path.join(MODEL_DIR, 'features.json'), 'w') as f:
        json.dump(features, f)
    with open(os.path.join(MODEL_DIR, 'lookup_tables.json'), 'w') as f:
        json.dump({
            'cause_stats': _CAUSE_STATS,
            'corridor_stats': _CORRIDOR_STATS,
            'junction_stats': _JUNCTION_STATS,
            'zone_stats': _ZONE_STATS,
        }, f)

    print("\nDone. Models saved to /models/")
