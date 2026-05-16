import sys, os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

import reconciler

STATIONS = [{"station_id": "S001", "station_name": "Test Station"}]

def test_f_to_c_conversion():
    result = reconciler._f_to_c(76.1)
    assert abs(result - 24.5) < 0.01

def test_humidity_normalization():
    api_row = {"station": "S001", "day": "2026-04-01", "temp_f": 76.1, "humidity": 0.68}
    local_row = {"station_id": "S001", "date": "2026-04-01", "temp_c": 24.5, "humidity_pct": 68.0}
    r = reconciler.reconcile([local_row], [api_row], STATIONS)
    canon = r["reconciled"][0]
    assert canon["humidity_pct"] == 68.0

def test_disagreement_detection():
    local_row = {"station_id": "S001", "date": "2026-04-02", "temp_c": 24.5, "humidity_pct": 68.0}
    api_row = {"station": "S001", "day": "2026-04-02", "temp_f": 82.0, "humidity": 0.68}  # 82F = 27.8C
    r = reconciler.reconcile([local_row], [api_row], STATIONS)
    assert r["summary"]["disagreed"] == 1
    diff = r["disagreements"][0]
    assert "fields" in diff
    fields = [f["field"] for f in diff["fields"]]
    assert "temp_c" in fields

def test_agreed_rows_counted():
    local = [{"station_id": "S001", "date": "2026-04-01", "temp_c": 24.5, "humidity_pct": 68.0}]
    api = [{"station": "S001", "day": "2026-04-01", "temp_f": 76.1, "humidity": 0.68}]
    r = reconciler.reconcile(local, api, STATIONS)
    assert r["summary"]["agreed"] == 1
    assert r["summary"]["disagreed"] == 0
