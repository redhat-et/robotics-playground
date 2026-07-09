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


def test_config_returns_defaults():
    client = TestClient(app)
    response = client.get("/api/config")
    assert response.status_code == 200
    assert response.json() == {"wsUrl": "", "rerunViewerUrl": "", "rerunGrpcUrl": ""}


def test_config_returns_urls_from_env(monkeypatch):
    monkeypatch.setenv("WS_EXTERNAL_URL", "wss://backend.example.com")
    monkeypatch.setenv("RERUN_VIEWER_URL", "https://rerun-web.example.com")
    monkeypatch.setenv("RERUN_GRPC_URL", "https://rerun-grpc.example.com")
    client = TestClient(app)
    response = client.get("/api/config")
    assert response.status_code == 200
    assert response.json() == {
        "wsUrl": "wss://backend.example.com",
        "rerunViewerUrl": "https://rerun-web.example.com",
        "rerunGrpcUrl": "https://rerun-grpc.example.com",
    }
