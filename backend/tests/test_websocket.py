from __future__ import annotations

from unittest.mock import MagicMock, patch

from fastapi.testclient import TestClient

from robotics_playground.main import app


@patch("robotics_playground.rerun_logger.rr")
def test_websocket_instruction_flow(mock_rr: MagicMock):
    with TestClient(app) as client, client.websocket_connect("/ws/sessions/test") as ws:
        ws.send_json({"type": "instruction", "text": "wave"})
        for _ in range(10):
            data = ws.receive_json()
            if data["type"] == "instruction_ack":
                break
        assert data["type"] == "instruction_ack"
        assert data["status"] == "received"
        assert data["text"] == "wave"


@patch("robotics_playground.rerun_logger.rr")
def test_websocket_connect_and_close(mock_rr: MagicMock):
    with TestClient(app) as client, client.websocket_connect("/ws/sessions/test"):
        pass  # connect and immediately close — should not crash


@patch("robotics_playground.rerun_logger.rr")
def test_websocket_sim_control(mock_rr: MagicMock):
    with TestClient(app) as client, client.websocket_connect("/ws/sessions/test") as ws:
        ws.send_json({"type": "sim_control", "action": "play"})
        data = ws.receive_json()
        assert data["type"] == "status"
        assert data["state"] in ("running", "idle")


@patch("robotics_playground.rerun_logger.rr")
def test_websocket_status_includes_step(mock_rr: MagicMock):
    with TestClient(app) as client, client.websocket_connect("/ws/sessions/test") as ws:
        data = ws.receive_json()
        assert data["type"] == "status"
        assert "step" in data
        assert "state" in data
