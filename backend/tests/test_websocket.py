from __future__ import annotations

from unittest.mock import MagicMock, patch

from fastapi.testclient import TestClient

from robotics_playground.main import app


@patch("robotics_playground.rerun_logger.rr")
def test_websocket_connect_receives_status(mock_rr: MagicMock):
    with TestClient(app) as client, client.websocket_connect("/ws/sessions/test") as ws:
        data = ws.receive_json()
        assert data["type"] == "status"
        assert "state" in data
        assert "step" in data
        assert "instruction" in data
        assert "bridge_status" in data
        assert "model_id" in data
        assert data["bridge_status"] == "connected"


@patch("robotics_playground.rerun_logger.rr")
def test_websocket_connect_and_close(mock_rr: MagicMock):
    with TestClient(app) as client, client.websocket_connect("/ws/sessions/test"):
        pass


@patch("robotics_playground.rerun_logger.rr")
def test_websocket_instruction_flow(mock_rr: MagicMock):
    with TestClient(app) as client, client.websocket_connect("/ws/sessions/test") as ws:
        _ = ws.receive_json()  # initial status
        ws.send_json({"type": "instruction", "text": "wave"})
        ack = ws.receive_json()
        assert ack["type"] == "instruction_ack"
        assert ack["status"] == "received"
        assert ack["text"] == "wave"


@patch("robotics_playground.rerun_logger.rr")
def test_websocket_sim_control_with_speed(mock_rr: MagicMock):
    with TestClient(app) as client, client.websocket_connect("/ws/sessions/test") as ws:
        _ = ws.receive_json()
        ws.send_json({"type": "sim_control", "action": "play", "speed": 2.0})
        status = ws.receive_json()
        assert status["type"] == "status"


@patch("robotics_playground.rerun_logger.rr")
def test_websocket_sim_control_play(mock_rr: MagicMock):
    with TestClient(app) as client, client.websocket_connect("/ws/sessions/test") as ws:
        ws.send_json({"type": "sim_control", "action": "play"})
        data = ws.receive_json()
        assert data["type"] == "status"


@patch("robotics_playground.rerun_logger.rr")
def test_websocket_malformed_json_ignored(mock_rr: MagicMock):
    with TestClient(app) as client, client.websocket_connect("/ws/sessions/test") as ws:
        ws.send_text("not valid json")
        data = ws.receive_json()
        assert data["type"] == "status"


@patch("robotics_playground.rerun_logger.rr")
def test_websocket_unknown_message_type_ignored(mock_rr: MagicMock):
    with TestClient(app) as client, client.websocket_connect("/ws/sessions/test") as ws:
        ws.send_json({"type": "unknown_type", "data": 123})
        data = ws.receive_json()
        assert data["type"] == "status"


@patch("robotics_playground.rerun_logger.rr")
def test_websocket_multiple_instructions(mock_rr: MagicMock):
    with TestClient(app) as client, client.websocket_connect("/ws/sessions/test") as ws:
        ws.send_json({"type": "instruction", "text": "first"})
        acks = []
        for _ in range(20):
            data = ws.receive_json()
            if data["type"] == "instruction_ack":
                acks.append(data)
                break

        ws.send_json({"type": "instruction", "text": "second"})
        for _ in range(20):
            data = ws.receive_json()
            if data["type"] == "instruction_ack":
                acks.append(data)
                break

        assert len(acks) == 2
        assert acks[0]["text"] == "first"
        assert acks[1]["text"] == "second"


@patch("robotics_playground.rerun_logger.rr")
def test_websocket_select_model_silently_ignored_when_invalid(mock_rr: MagicMock):
    """select_model with invalid model_id is silently ignored (no error, no ack)."""
    with TestClient(app) as client, client.websocket_connect("/ws/sessions/test") as ws:
        _ = ws.receive_json()  # initial status
        ws.send_json({"type": "select_model", "model_id": "nonexistent"})
        # Should just receive next status (no crash, no special message)
        data = ws.receive_json()
        assert data["type"] == "status"


def test_api_models_with_populated_config():
    """Test /api/models endpoint with actual model entries in config."""
    from robotics_playground.config import ModelConfig, PlaygroundConfig, PolicyConfig
    from robotics_playground.main import app

    test_config = PlaygroundConfig(
        policy=PolicyConfig(
            type="openpi",
            default_model="dreamzero-v1",
            models={
                "dreamzero-v1": ModelConfig(
                    name="DreamZero",
                    endpoint="ws://dreamzero:8080/v1/realtime/robot/openpi",
                    action_horizon=4,
                ),
                "pi05-v1": ModelConfig(
                    name="pi0.5",
                    endpoint="ws://pi05:8080/",
                    action_horizon=8,
                ),
            },
        )
    )

    with (
        patch("robotics_playground.main.config", test_config),
        patch("robotics_playground.rerun_logger.rr"),
        TestClient(app) as client,
    ):
        response = client.get("/api/models?type=robotics")
        assert response.status_code == 200
        data = response.json()
        assert "models" in data
        models = data["models"]
        assert len(models) == 2

        # Verify both models are present with correct IDs and names
        model_ids = {m["id"] for m in models}
        assert model_ids == {"dreamzero-v1", "pi05-v1"}

        dreamzero = next(m for m in models if m["id"] == "dreamzero-v1")
        assert dreamzero["name"] == "DreamZero"
        assert dreamzero["type"] == "robotics"

        pi05 = next(m for m in models if m["id"] == "pi05-v1")
        assert pi05["name"] == "pi0.5"
        assert pi05["type"] == "robotics"
