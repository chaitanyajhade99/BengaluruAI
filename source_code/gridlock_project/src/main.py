import os
import sys
import json
import pickle
import random
import pandas as pd
import numpy as np
from datetime import datetime, timedelta
from fastapi import FastAPI, HTTPException
from fastapi.responses import FileResponse, HTMLResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel

# Add current directory to path to import local modules
SRC_DIR = os.path.dirname(os.path.abspath(__file__))
if SRC_DIR not in sys.path:
    sys.path.insert(0, SRC_DIR)

import database
import pipeline

from fastapi.middleware.cors import CORSMiddleware

app = FastAPI(title="BengaluruAI Traffic Command API")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Setup folder paths
PROJECT_DIR = os.path.dirname(SRC_DIR)
WORKSPACE_DIR = os.path.dirname(os.path.dirname(PROJECT_DIR))
DASHBOARD_PATH = os.path.join(PROJECT_DIR, "dashboard", "index.html")
CSV_PATH = os.path.join(WORKSPACE_DIR, "Astram event data_anonymized - Astram event data_anonymizedb40ac87 (1).csv")

# Global ML models
clf = None
reg = None
features = []
lookup_tables = {}

# Pre-computed analytics from CSV (computed on startup)
analytics_cache = {}

class PredictionRequest(BaseModel):
    event_type: str
    event_cause: str
    corridor: str
    priority: str
    latitude: float
    longitude: float
    junction: str = None
    zone: str = None
    veh_type: str = None
    start_datetime: str

class FeedbackRequest(BaseModel):
    event_id: str
    actual_duration: float
    actual_closure: bool

# SQLite-based PostEventLearner adaptor to run pipeline.py predictions seamlessly
class SQLitePostEventLearner:
    def correction_factor(self, cause, corridor, hour_IST):
        is_peak = (8 <= hour_IST <= 11) or (17 <= hour_IST <= 21)
        return database.get_correction_factor(cause, corridor, is_peak)

def compute_analytics_from_csv():
    """Pre-compute all chart data from the CSV dataset on startup."""
    global analytics_cache
    
    if not os.path.exists(CSV_PATH):
        print(f"Warning: CSV not found at {CSV_PATH}. Using fallback analytics.")
        analytics_cache = {}
        return
    
    try:
        df = pd.read_csv(CSV_PATH)
        
        # Parse datetimes
        IST_OFFSET = timedelta(hours=5, minutes=30)
        df['start_dt'] = pd.to_datetime(df['start_datetime'], utc=True, errors='coerce')
        df['start_IST'] = df['start_dt'] + IST_OFFSET
        
        end_time = pd.to_datetime(df['closed_datetime'].fillna(df['resolved_datetime']), utc=True, errors='coerce')
        df['duration_mins'] = (end_time - df['start_dt']).dt.total_seconds() / 60
        
        total_events = len(df)
        total_closures = int(df['requires_road_closure'].sum()) if 'requires_road_closure' in df.columns else 0
        
        # Median resolution (only valid durations)
        valid_dur = df.loc[(df['duration_mins'] > 0) & (df['duration_mins'] < 100000), 'duration_mins']
        median_res = round(valid_dur.median(), 1) if len(valid_dur) > 0 else 64
        
        # Hourly distribution (IST)
        hourly_ist = df['start_IST'].dt.hour.value_counts().sort_index()
        hourly_data = {str(int(h)): int(c) for h, c in hourly_ist.items()}
        
        # Cause counts
        cause_counts = df['event_cause'].str.strip().str.lower().value_counts()
        cause_data = {str(k): int(v) for k, v in cause_counts.items()}
        
        # Day of week
        dow_counts = df['start_IST'].dt.dayofweek.value_counts().sort_index()
        dow_data = {str(int(d)): int(c) for d, c in dow_counts.items()}
        
        # Closure rate by cause
        closure_by_cause = []
        df['event_cause_clean'] = df['event_cause'].str.strip().str.lower()
        for cause, grp in df.groupby('event_cause_clean'):
            closure_by_cause.append({
                "cause": cause,
                "count": int(len(grp)),
                "closure_rate": round(float(grp['requires_road_closure'].mean()), 3) if 'requires_road_closure' in grp.columns else 0,
                "median_dur": round(float(grp.loc[(grp['duration_mins'] > 0) & (grp['duration_mins'] < 100000), 'duration_mins'].median()), 1) if len(grp.loc[(grp['duration_mins'] > 0) & (grp['duration_mins'] < 100000)]) > 0 else 0
            })
        closure_by_cause.sort(key=lambda x: x['closure_rate'], reverse=True)
        
        # Corridor stats
        corridor_data = []
        for corr, grp in df.groupby('corridor'):
            if pd.isna(corr):
                continue
            high_prio_rate = float((grp['priority'] == 'High').mean()) if 'priority' in grp.columns else 0
            closure_rate = float(grp['requires_road_closure'].mean()) if 'requires_road_closure' in grp.columns else 0
            risk = round(0.4 * closure_rate + 0.4 * high_prio_rate + 0.2 * (len(grp) / total_events), 3)
            corridor_data.append({
                "corridor": str(corr),
                "event_count": int(len(grp)),
                "closure_rate": round(closure_rate, 3),
                "corridor_risk": risk,
                "high_priority_rate": round(high_prio_rate, 3)
            })
        corridor_data.sort(key=lambda x: x['event_count'], reverse=True)
        
        # Junction hotspots
        junction_data = []
        junc_df = df[df['junction'].notna()].copy()
        for junc, grp in junc_df.groupby('junction'):
            if len(grp) >= 10:
                junction_data.append({
                    "junction": str(junc),
                    "count": int(len(grp)),
                    "closure_rate": round(float(grp['requires_road_closure'].mean()), 3) if 'requires_road_closure' in grp.columns else 0,
                    "lat": round(float(grp['latitude'].mean()), 6),
                    "lon": round(float(grp['longitude'].mean()), 6)
                })
        junction_data.sort(key=lambda x: x['count'], reverse=True)
        junction_data = junction_data[:20]  # Top 20
        
        # Unique values for dropdowns
        corridors_list = sorted(df['corridor'].dropna().unique().tolist())
        causes_list = sorted(df['event_cause_clean'].unique().tolist())
        junctions_list = sorted(junc_df['junction'].unique().tolist())
        zones_list = sorted(df['zone'].dropna().unique().tolist())
        
        analytics_cache = {
            "total_events": total_events,
            "total_closures": total_closures,
            "closure_rate_pct": round((total_closures / total_events) * 100, 2) if total_events > 0 else 0,
            "median_resolution_mins": median_res,
            "hourly_ist": hourly_data,
            "cause_counts": cause_data,
            "dow_counts": dow_data,
            "closure_by_cause": closure_by_cause,
            "corridor_stats": corridor_data,
            "junction_hotspots": junction_data,
            "dropdowns": {
                "corridors": corridors_list,
                "causes": causes_list,
                "junctions": junctions_list,
                "zones": zones_list
            }
        }
        print(f"Analytics computed: {total_events} events, {total_closures} closures, {len(junction_data)} hotspots")
    except Exception as e:
        print(f"Error computing analytics: {e}")
        analytics_cache = {}

@app.on_event("startup")
def startup_event():
    global clf, reg, features, lookup_tables
    
    # 1. Initialize SQLite Database
    database.init_db()
    
    # 2. Load ML Models
    models_dir = os.path.join(PROJECT_DIR, "models")
    
    try:
        with open(os.path.join(models_dir, "classifier.pkl"), "rb") as f:
            clf_bundle = pickle.load(f)
            clf = clf_bundle["model"]
            
        with open(os.path.join(models_dir, "regressor.pkl"), "rb") as f:
            reg = pickle.load(f)
            
        with open(os.path.join(models_dir, "features.json"), "r") as f:
            features = json.load(f)
            
        with open(os.path.join(models_dir, "lookup_tables.json"), "r") as f:
            lookup_tables = json.load(f)
            
        # 3. Populate pipeline's statistics cache with tables
        pipeline._CAUSE_STATS = lookup_tables.get("cause_stats", {})
        pipeline._CORRIDOR_STATS = lookup_tables.get("corridor_stats", {})
        pipeline._JUNCTION_STATS = lookup_tables.get("junction_stats", {})
        pipeline._ZONE_STATS = lookup_tables.get("zone_stats", {})
        print("Models and lookup tables loaded successfully!")
    except Exception as e:
        print(f"Error loading ML models: {e}. Running in heuristic-only mode.")
    
    # 4. Compute analytics from CSV
    compute_analytics_from_csv()

@app.get("/")
def get_dashboard():
    if os.path.exists(DASHBOARD_PATH):
        return FileResponse(DASHBOARD_PATH, media_type="text/html")
    raise HTTPException(status_code=404, detail="Dashboard file not found.")

@app.get("/api/dashboard-stats")
def get_dashboard_stats():
    conn = database.get_db()
    cursor = conn.cursor()
    
    # SQLite counts
    db_total = cursor.execute("SELECT COUNT(*) FROM active_events").fetchone()[0]
    db_closures = cursor.execute("SELECT COUNT(*) FROM active_events WHERE COALESCE(actual_closure, predicted_closure) = 1").fetchone()[0]
    
    # Calculate median resolution time of logged items
    logged_durations = [r[0] for r in cursor.execute("SELECT actual_duration FROM active_events WHERE actual_duration IS NOT NULL").fetchall()]
    conn.close()
    
    # Calibration metrics
    total_logged = len(logged_durations)
    if total_logged > 0:
        import statistics
        median_res = int(statistics.median(logged_durations))
    else:
        median_res = analytics_cache.get("median_resolution_mins", 64)
        
    # We anchor the starting point to the full dataset stats
    base_events = analytics_cache.get("total_events", 8173)
    base_closures = analytics_cache.get("total_closures", 676)
    net_new_events = max(0, db_total - 8)
    net_new_closures = max(0, db_closures - 5)

    return {
        "total_events": base_events + net_new_events,
        "closure_events": base_closures + net_new_closures,
        "closure_rate_pct": round(((base_closures + net_new_closures) / (base_events + net_new_events)) * 100, 2),
        "median_resolution_mins": median_res,
        "auc_score": 0.776,
        "r2_score": 0.529,
        "db_events": db_total,
        "db_pending": db_total - total_logged
    }

@app.get("/api/event-analytics")
def get_event_analytics():
    """Return pre-computed chart data from the CSV dataset."""
    if not analytics_cache:
        raise HTTPException(status_code=500, detail="Analytics not yet computed. CSV may be missing.")
    return analytics_cache

@app.get("/api/active-events")
def get_active_events():
    """Return events that have not received feedback yet."""
    events = database.get_active_events()
    return [{
        "id": e["id"],
        "cause": e["event_cause"],
        "corridor": e["corridor"],
        "event_type": e["event_type"],
        "priority": e["priority"],
        "predicted_duration": int(e["predicted_duration"]),
        "closure_prob": round(e["closure_prob"] * 100, 1),
        "alert_tier": e["alert_tier"],
        "officers": e["officers"],
        "barricades": e["barricades"],
        "diversion": bool(e["diversion"]),
        "is_peak": bool(e["is_peak"]),
        "logged_at": e["logged_at"]
    } for e in events]

@app.get("/api/correction-factors")
def get_correction_factors():
    """Return correction factor summaries for the learning dashboard."""
    factors = database.get_correction_factors_summary()
    return factors

@app.post("/api/predict")
def run_predict(req: PredictionRequest):
    if not clf or not reg:
        raise HTTPException(status_code=500, detail="Models not loaded on server.")
        
    try:
        # Check if peak hour
        hour_IST = datetime.fromisoformat(req.start_datetime.replace('Z', '')).hour
        is_peak = (8 <= hour_IST <= 11) or (17 <= hour_IST <= 21)
        
        inputs = {
            "event_type": req.event_type,
            "event_cause": req.event_cause,
            "corridor": req.corridor,
            "priority": req.priority,
            "latitude": req.latitude,
            "longitude": req.longitude,
            "junction": req.junction,
            "zone": req.zone,
            "veh_type": req.veh_type,
            "start_datetime": req.start_datetime,
            "is_peak": is_peak
        }
        
        # Instantiate learner using SQLite queries
        learner = SQLitePostEventLearner()
        
        # Run prediction
        res = pipeline.predict_event(
            clf=clf,
            reg=reg,
            features=features,
            learner=learner,
            event_cause=req.event_cause,
            corridor=req.corridor,
            event_type=req.event_type,
            start_datetime_IST=req.start_datetime,
            latitude=req.latitude,
            longitude=req.longitude,
            priority=req.priority,
            junction=req.junction,
            zone=req.zone,
            veh_type=req.veh_type
        )
        
        # Insert as active prediction in database
        event_id = f"EVT-{random.randint(1000, 9999)}"
        pred_dur = res["predicted_duration_mins"]
        closure_prob = res["closure_probability_pct"] / 100.0
        
        database.add_prediction(event_id, inputs, pred_dur, closure_prob, res)
        
        return {
            "event_id": event_id,
            "alert_tier": res["alert_tier"],
            "impact_index": res["impact_index"],
            "closure_probability_pct": res["closure_probability_pct"],
            "predicted_duration_mins": pred_dur,
            "predicted_duration_hrs": res["predicted_duration_hrs"],
            "officers_recommended": res["officers_recommended"],
            "barricades_recommended": res["barricades_recommended"],
            "activate_diversion": res["activate_diversion"],
            "target_response_mins": res["target_response_mins"],
            "historical": res["historical"],
            "correction_applied_mins": res["correction_applied_mins"]
        }
    except Exception as e:
        raise HTTPException(status_code=400, detail=f"Prediction error: {str(e)}")

@app.post("/api/log-feedback")
def run_log_feedback(req: FeedbackRequest):
    event = database.get_event(req.event_id)
    if not event:
        raise HTTPException(status_code=404, detail="Event not found.")
        
    database.log_feedback(req.event_id, req.actual_duration, req.actual_closure)
    
    # Calculate this instance's error residual
    error_mins = req.actual_duration - event["predicted_duration"]
    
    return {
        "status": "success",
        "error_mins": round(error_mins, 1),
        "cause": event["event_cause"],
        "corridor": event["corridor"]
    }

@app.get("/api/learning-logs")
def get_learning_logs():
    events = database.get_all_events()
    logs = []
    for e in events:
        logs.append({
            "id": e["id"],
            "cause": e["event_cause"],
            "corridor": e["corridor"],
            "pred": int(e["predicted_duration"]),
            "actual": int(e["actual_duration"]) if e["actual_duration"] is not None else None,
            "predClose": bool(e["predicted_closure"]),
            "actualClose": bool(e["actual_closure"]) if e["actual_closure"] is not None else None,
            "tier": e["alert_tier"],
            "officers": e["officers"],
            "barricades": e["barricades"],
            "diversion": bool(e["diversion"]),
            "logged_at": e["logged_at"]
        })
    return logs

@app.post("/api/simulate-incident")
def simulate_incident():
    if not os.path.exists(CSV_PATH):
        raise HTTPException(status_code=500, detail="Historical dataset not found.")
        
    try:
        # Load sample row
        df = pd.read_csv(CSV_PATH)
        # Filter for rows that have valid closed/resolved dates to get actual resolution durations
        df["start_dt"] = pd.to_datetime(df["start_datetime"], utc=True, errors="coerce")
        end_time = pd.to_datetime(df["closed_datetime"].fillna(df["resolved_datetime"]), utc=True, errors="coerce")
        df["duration_mins"] = (end_time - df["start_dt"]).dt.total_seconds() / 60
        
        valid_df = df[df["duration_mins"] > 5].copy()
        if valid_df.empty:
            valid_df = df
            
        row = valid_df.sample(n=1).iloc[0]
        
        # Clean/normalize
        cause = str(row["event_cause"]).strip().lower()
        if cause == 'debris': cause = 'debris' # Normalized
        
        # Replace date with current time
        simulated_time = datetime.now().isoformat()
        
        # Prepare inputs
        inputs = {
            "event_type": str(row["event_type"]).strip().lower(),
            "event_cause": cause,
            "corridor": str(row["corridor"]) if pd.notna(row["corridor"]) else "Non-corridor",
            "priority": str(row["priority"]) if pd.notna(row["priority"]) else "Low",
            "latitude": float(row["latitude"]) if pd.notna(row["latitude"]) else 12.9716,
            "longitude": float(row["longitude"]) if pd.notna(row["longitude"]) else 77.5946,
            "junction": str(row["junction"]) if pd.notna(row["junction"]) else None,
            "zone": str(row["zone"]) if pd.notna(row["zone"]) else None,
            "veh_type": str(row["veh_type"]).strip().lower() if pd.notna(row["veh_type"]) else None,
            "start_datetime": simulated_time,
            "is_peak": (8 <= datetime.now().hour <= 11) or (17 <= datetime.now().hour <= 21)
        }
        
        # Run prediction
        learner = SQLitePostEventLearner()
        res = pipeline.predict_event(
            clf=clf,
            reg=reg,
            features=features,
            learner=learner,
            event_cause=inputs["event_cause"],
            corridor=inputs["corridor"],
            event_type=inputs["event_type"],
            start_datetime_IST=inputs["start_datetime"],
            latitude=inputs["latitude"],
            longitude=inputs["longitude"],
            priority=inputs["priority"],
            junction=inputs["junction"],
            zone=inputs["zone"],
            veh_type=inputs["veh_type"]
        )
        
        # Save to SQLite
        event_id = f"EVT-{random.randint(1000, 9999)}"
        database.add_prediction(event_id, inputs, res["predicted_duration_mins"], res["closure_probability_pct"] / 100.0, res)
        
        # Return prediction + the real duration for dynamic UI pre-fill capability
        return {
            "event_id": event_id,
            "inputs": inputs,
            "prediction": res,
            "true_actual_duration_mins": int(row["duration_mins"]) if pd.notna(row["duration_mins"]) else 60,
            "true_actual_closure": bool(row["requires_road_closure"]) if pd.notna(row["requires_road_closure"]) else False
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Simulation failed: {str(e)}")

if __name__ == "__main__":
    import uvicorn
    uvicorn.run("main:app", host="127.0.0.1", port=8000, reload=True)
