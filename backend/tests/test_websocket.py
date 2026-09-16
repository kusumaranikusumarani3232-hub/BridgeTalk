import pytest
from fastapi.testclient import TestClient
from app.main import app

def test_health_check():
    client = TestClient(app)
    response = client.get("/api/health")
    assert response.status_code == 200
    data = response.json()
    assert data["status"] == "healthy"
    assert data["app"] == "BridgeTalk"

def test_demo_data_endpoint():
    client = TestClient(app)
    response = client.get("/api/demo-data")
    assert response.status_code == 200
    data = response.json()
    assert len(data) >= 2
    assert data[0]["speaker"] == "person_a"
    assert data[1]["speaker"] == "person_b"

def test_translate_endpoint():
    client = TestClient(app)
    response = client.post(
        "/api/translate",
        json={"text": "Good morning", "source_lang": "en", "target_lang": "hi"}
    )
    assert response.status_code == 200
    data = response.json()
    assert "translation" in data
    assert len(data["translation"]) > 0
