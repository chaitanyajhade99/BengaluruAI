import os
import sqlite3
from datetime import datetime

DB_PATH = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), 'bengaluru_ai.db')

def get_db():
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    return conn

def init_db():
    conn = get_db()
    cursor = conn.cursor()
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS active_events (
            id TEXT PRIMARY KEY,
            event_cause TEXT NOT NULL,
            corridor TEXT NOT NULL,
            event_type TEXT NOT NULL,
            priority TEXT NOT NULL,
            start_datetime TEXT NOT NULL,
            latitude REAL NOT NULL,
            longitude REAL NOT NULL,
            predicted_duration REAL NOT NULL,
            predicted_closure INTEGER NOT NULL,
            closure_prob REAL NOT NULL,
            actual_duration REAL,
            actual_closure INTEGER,
            alert_tier TEXT NOT NULL,
            officers INTEGER NOT NULL,
            barricades INTEGER NOT NULL,
            diversion INTEGER NOT NULL,
            is_peak INTEGER NOT NULL,
            logged_at TEXT NOT NULL
        )
    """)
    conn.commit()

    # Seed initial learning records if empty
    cursor.execute("SELECT COUNT(*) FROM active_events")
    if cursor.fetchone()[0] == 0:
        initial_records = [
            ("EVT-1081", "public_event", "Bellary Road 1", "planned", "High", "2024-03-14 18:00", 12.98, 77.58, 78.0, 1, 0.62, 94.0, 1, "HIGH", 6, 4, 1, 1),
            ("EVT-1082", "vip_movement", "Tumkur Road", "planned", "High", "2024-03-14 10:00", 13.02, 77.54, 52.0, 1, 0.78, 45.0, 1, "CRITICAL", 9, 5, 1, 1),
            ("EVT-1083", "construction", "Mysore Road", "planned", "High", "2024-03-14 08:00", 12.97, 77.53, 210.0, 1, 0.38, 340.0, 1, "HIGH", 5, 2, 1, 1),
            ("EVT-1084", "vehicle_breakdown", "ORR East 1", "unplanned", "Low", "2024-03-14 09:30", 12.91, 77.62, 38.0, 0, 0.08, 41.0, 0, "LOW", 3, 0, 0, 1),
            ("EVT-1085", "tree_fall", "Non-corridor", "unplanned", "Low", "2024-03-14 14:00", 13.00, 77.66, 125.0, 1, 0.39, 89.0, 0, "MEDIUM", 2, 1, 0, 0),
            ("EVT-1086", "water_logging", "Hosur Road", "unplanned", "High", "2024-03-14 17:30", 12.95, 77.58, 180.0, 0, 0.08, 260.0, 1, "MEDIUM", 2, 1, 0, 1),
            ("EVT-1087", "protest", "Old Madras Road", "unplanned", "High", "2024-03-14 12:00", 13.04, 77.62, 22.0, 1, 0.40, 30.0, 1, "HIGH", 4, 2, 1, 0),
            ("EVT-1088", "accident", "Bellary Road 2", "unplanned", "Low", "2024-03-14 15:00", 13.09, 77.50, 44.0, 0, 0.03, 38.0, 0, "LOW", 1, 0, 0, 0),
        ]
        now_str = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        cursor.executemany("""
            INSERT INTO active_events (
                id, event_cause, corridor, event_type, priority, start_datetime,
                latitude, longitude, predicted_duration, predicted_closure,
                closure_prob, actual_duration, actual_closure, alert_tier,
                officers, barricades, diversion, is_peak, logged_at
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """, [r + (now_str,) for r in initial_records])
        conn.commit()

    conn.close()

def add_prediction(event_id, inputs, pred_dur, closure_prob, rec):
    conn = get_db()
    cursor = conn.cursor()
    now_str = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    cursor.execute("""
        INSERT INTO active_events (
            id, event_cause, corridor, event_type, priority, start_datetime,
            latitude, longitude, predicted_duration, predicted_closure,
            closure_prob, actual_duration, actual_closure, alert_tier,
            officers, barricades, diversion, is_peak, logged_at
        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, NULL, NULL, ?, ?, ?, ?, ?, ?)
    """, (
        event_id,
        inputs['event_cause'],
        inputs['corridor'],
        inputs['event_type'],
        inputs['priority'],
        inputs['start_datetime'],
        inputs['latitude'],
        inputs['longitude'],
        pred_dur,
        1 if closure_prob > 0.3 else 0,
        closure_prob,
        rec['alert_tier'],
        rec['officers_recommended'],
        rec['barricades_recommended'],
        1 if rec['activate_diversion'] else 0,
        1 if inputs['is_peak'] else 0,
        now_str
    ))
    conn.commit()
    conn.close()

def log_feedback(event_id, actual_duration, actual_closure):
    conn = get_db()
    cursor = conn.cursor()
    cursor.execute("""
        UPDATE active_events
        SET actual_duration = ?, actual_closure = ?
        WHERE id = ?
    """, (actual_duration, 1 if actual_closure else 0, event_id))
    conn.commit()
    conn.close()

def get_event(event_id):
    conn = get_db()
    cursor = conn.cursor()
    cursor.execute("SELECT * FROM active_events WHERE id = ?", (event_id,))
    row = cursor.fetchone()
    conn.close()
    return dict(row) if row else None

def get_all_events():
    conn = get_db()
    cursor = conn.cursor()
    cursor.execute("SELECT * FROM active_events ORDER BY logged_at DESC")
    rows = cursor.fetchall()
    conn.close()
    return [dict(r) for r in rows]

def get_active_events():
    """Return events where feedback has not yet been logged."""
    conn = get_db()
    cursor = conn.cursor()
    cursor.execute("""
        SELECT * FROM active_events
        WHERE actual_duration IS NULL
        ORDER BY logged_at DESC
    """)
    rows = cursor.fetchall()
    conn.close()
    return [dict(r) for r in rows]

def get_event_count():
    """Return total event count for the live badge."""
    conn = get_db()
    cursor = conn.cursor()
    count = cursor.execute("SELECT COUNT(*) FROM active_events").fetchone()[0]
    conn.close()
    return count

def get_correction_factors_summary():
    """Return per-cause correction factor summaries for the learning dashboard."""
    conn = get_db()
    cursor = conn.cursor()
    cursor.execute("""
        SELECT event_cause,
               corridor,
               COUNT(*) as n,
               ROUND(AVG(actual_duration - predicted_duration), 1) as avg_error,
               ROUND(AVG(actual_duration), 1) as avg_actual,
               ROUND(AVG(predicted_duration), 1) as avg_predicted
        FROM active_events
        WHERE actual_duration IS NOT NULL
        GROUP BY event_cause, corridor
        ORDER BY ABS(AVG(actual_duration - predicted_duration)) DESC
    """)
    rows = cursor.fetchall()
    conn.close()
    return [dict(r) for r in rows]

def get_correction_factor(cause, corridor, is_peak):
    conn = get_db()
    cursor = conn.cursor()
    cursor.execute("""
        SELECT AVG(actual_duration - (predicted_duration - COALESCE(actual_duration, 0) * 0.0))
        FROM active_events
        WHERE actual_duration IS NOT NULL
          AND event_cause = ?
          AND corridor = ?
          AND is_peak = ?
    """, (cause, corridor, 1 if is_peak else 0))
    val = cursor.fetchone()[0]
    conn.close()
    # If there are no historical errors logged, return 0.0
    return float(val) if val is not None else 0.0
