"""Tests for REST API endpoints using an in-memory SQLite database."""
from datetime import datetime

import pytest

from app.db.models import PostureEvent, Reading


# --- helpers ---

def seed_readings(db, sensor="temp_c", count=5, base_value=20.0):
    for i in range(count):
        db.add(Reading(
            ts=datetime(2024, 1, 1, 12, i, 0),
            sensor=sensor,
            value=base_value + i,
            unit="C",
        ))
    db.commit()


# --- /readings/query ---

def test_query_readings_returns_all(client_and_db):
    client, db = client_and_db
    seed_readings(db)
    resp = client.get("/readings/query?sensor_name=temp_c")
    assert resp.status_code == 200
    data = resp.json()
    assert data["total"] == 5
    assert len(data["data"]) == 5


def test_query_readings_unknown_sensor_returns_empty(client_and_db):
    client, db = client_and_db
    resp = client.get("/readings/query?sensor_name=made_up_sensor")
    assert resp.status_code == 200
    assert resp.json()["total"] == 0


def test_query_readings_time_filter(client_and_db):
    client, db = client_and_db
    seed_readings(db)  # rows at 12:00, 12:01, 12:02, 12:03, 12:04
    resp = client.get(
        "/readings/query?sensor_name=temp_c"
        "&start_time=2024-01-01T12:02:00"
        "&end_time=2024-01-01T12:03:00"
    )
    assert resp.status_code == 200
    assert resp.json()["total"] == 2  # 12:02 and 12:03


def test_query_readings_pagination(client_and_db):
    client, db = client_and_db
    seed_readings(db, count=10)
    resp = client.get("/readings/query?sensor_name=temp_c&page=1&page_size=3")
    assert resp.status_code == 200
    data = resp.json()
    assert len(data["data"]) == 3
    assert data["total"] == 10
    assert data["total_pages"] == 4


def test_query_readings_second_page(client_and_db):
    client, db = client_and_db
    seed_readings(db, count=10)
    resp = client.get("/readings/query?sensor_name=temp_c&page=2&page_size=3")
    assert resp.status_code == 200
    assert len(resp.json()["data"]) == 3


def test_query_readings_last_page_partial(client_and_db):
    client, db = client_and_db
    seed_readings(db, count=10)
    resp = client.get("/readings/query?sensor_name=temp_c&page=4&page_size=3")
    assert resp.status_code == 200
    assert len(resp.json()["data"]) == 1  # 10 rows, page 4 of 3 = 1 row


def test_query_readings_response_shape(client_and_db):
    client, db = client_and_db
    seed_readings(db, count=1)
    resp = client.get("/readings/query?sensor_name=temp_c")
    row = resp.json()["data"][0]
    assert "id" in row
    assert "timestamp" in row
    assert "sensor" in row
    assert "value" in row


def test_query_readings_ordered_newest_first(client_and_db):
    client, db = client_and_db
    seed_readings(db, count=5)
    resp = client.get("/readings/query?sensor_name=temp_c")
    timestamps = [r["timestamp"] for r in resp.json()["data"]]
    assert timestamps == sorted(timestamps, reverse=True)


# --- /readings/export/csv ---

def test_export_csv_returns_csv_content_type(client_and_db):
    client, db = client_and_db
    seed_readings(db)
    resp = client.get("/readings/export/csv?sensor_name=temp_c")
    assert resp.status_code == 200
    assert "text/csv" in resp.headers["content-type"]


def test_export_csv_has_correct_headers(client_and_db):
    client, db = client_and_db
    resp = client.get("/readings/export/csv")
    first_line = resp.text.strip().split("\n")[0]
    assert first_line == "id,timestamp,sensor,value,unit,device_ts_ms"


def test_export_csv_row_count(client_and_db):
    client, db = client_and_db
    seed_readings(db, count=5)
    resp = client.get("/readings/export/csv?sensor_name=temp_c")
    lines = [l for l in resp.text.strip().split("\n") if l]
    assert len(lines) == 6  # 1 header + 5 rows


def test_export_csv_empty_returns_only_header(client_and_db):
    client, db = client_and_db
    resp = client.get("/readings/export/csv?sensor_name=temp_c")
    lines = [l for l in resp.text.strip().split("\n") if l]
    assert len(lines) == 1


def test_export_csv_no_sensor_filter_returns_all(client_and_db):
    client, db = client_and_db
    seed_readings(db, sensor="temp_c", count=3)
    seed_readings(db, sensor="hum_pct", count=2)
    resp = client.get("/readings/export/csv")
    lines = [l for l in resp.text.strip().split("\n") if l]
    assert len(lines) == 6  # header + 5 rows


# --- /readings/posture/stats ---

def test_posture_stats_returns_correct_split(client_and_db):
    client, db = client_and_db
    now = datetime.now()
    db.add(PostureEvent(
        start_time=now.replace(hour=9, minute=0, second=0),
        end_time=now.replace(hour=10, minute=0, second=0),
        posture="sitting",
        duration_seconds=3600,
    ))
    db.add(PostureEvent(
        start_time=now.replace(hour=10, minute=0, second=0),
        end_time=now.replace(hour=11, minute=0, second=0),
        posture="standing",
        duration_seconds=3600,
    ))
    db.commit()

    resp = client.get("/readings/posture/stats")
    assert resp.status_code == 200
    data = resp.json()
    assert data["sitting_percentage"] == 50.0
    assert data["standing_percentage"] == 50.0
    assert data["sitting_seconds"] == 3600
    assert data["standing_seconds"] == 3600


def test_posture_stats_all_sitting(client_and_db):
    client, db = client_and_db
    now = datetime.now()
    db.add(PostureEvent(
        start_time=now.replace(hour=9),
        end_time=now.replace(hour=11),
        posture="sitting",
        duration_seconds=7200,
    ))
    db.commit()

    data = client.get("/readings/posture/stats").json()
    assert data["sitting_percentage"] == 100.0
    assert data["standing_percentage"] == 0.0


def test_posture_stats_no_data_returns_zeros(client_and_db):
    client, _ = client_and_db
    data = client.get("/readings/posture/stats").json()
    assert data["sitting_seconds"] == 0
    assert data["standing_seconds"] == 0


# --- /settings/posture ---

def test_get_posture_settings_returns_expected_keys(client_and_db):
    client, _ = client_and_db
    resp = client.get("/settings/posture")
    assert resp.status_code == 200
    data = resp.json()
    assert "sitting_height_cm" in data
    assert "standing_offset_cm" in data
    assert "standing_threshold_cm" in data
    assert "current_state" in data


def test_update_posture_settings(client_and_db):
    client, _ = client_and_db
    resp = client.put("/settings/posture", json={
        "sitting_height_cm": 75.0,
        "standing_offset_cm": 15.0,
    })
    assert resp.status_code == 200
    data = resp.json()
    assert data["sitting_height_cm"] == 75.0
    assert data["standing_threshold_cm"] == 90.0


def test_update_posture_settings_reflects_in_get(client_and_db):
    client, _ = client_and_db
    client.put("/settings/posture", json={
        "sitting_height_cm": 90.0,
        "standing_offset_cm": 20.0,
    })
    data = client.get("/settings/posture").json()
    assert data["sitting_height_cm"] == 90.0
    assert data["standing_threshold_cm"] == 110.0


def test_update_posture_settings_invalid_height(client_and_db):
    client, _ = client_and_db
    resp = client.put("/settings/posture", json={
        "sitting_height_cm": -10.0,
        "standing_offset_cm": 10.0,
    })
    assert resp.status_code == 422  # FastAPI validation error
