from fastapi.testclient import TestClient

from robotics_playground.main import app


def test_health_returns_ok():
    client = TestClient(app)
    response = client.get("/api/health")
    assert response.status_code == 200
    assert response.json() == {"status": "ok"}


def test_models_returns_list():
    client = TestClient(app)
    response = client.get("/api/models", params={"type": "robotics"})
    assert response.status_code == 200
    data = response.json()
    assert "models" in data
    assert len(data["models"]) >= 1
    assert data["models"][0]["id"] == "dreamzero-v1"
