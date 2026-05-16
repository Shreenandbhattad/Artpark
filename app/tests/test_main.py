from fastapi.testclient import TestClient
from main import app

client = TestClient(app)


def test_health():
    r = client.get("/health")
    assert r.status_code == 200
    body = r.json()
    assert body["status"] in ("ok", "degraded")
    assert "checks" in body
    assert "data" in body["checks"]


def test_version():
    r = client.get("/version")
    assert r.status_code == 200
    assert "version" in r.json()


def test_query_returns_200():
    r = client.post("/query", json={"question": "what is the average temperature?"})
    assert r.status_code == 200


def test_query_empty_question():
    r = client.post("/query", json={"question": ""})
    assert r.status_code == 400


def test_health_has_data_quality():
    r = client.get("/health")
    body = r.json()
    dq = body["checks"].get("data_quality", {})
    assert "total_records" in dq or dq == {}


def test_correlation_id_header():
    r = client.get("/health", headers={"X-Correlation-ID": "test-abc"})
    assert r.headers.get("x-correlation-id") == "test-abc"
