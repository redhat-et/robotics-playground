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


@patch("robotics_playground.rerun_logger.rr")
def test_websocket_connect_and_close(mock_rr: MagicMock):
    with TestClient(app) as client, client.websocket_connect("/ws/sessions/test"):
        pass


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
def test_websocket_instruction_ack_includes_text(mock_rr: MagicMock):
    with TestClient(app) as client, client.websocket_connect("/ws/sessions/test") as ws:
        ws.send_json({"type": "instruction", "text": "pick up the red block"})
        for _ in range(10):
            data = ws.receive_json()
            if data["type"] == "instruction_ack":
                break
        assert data["text"] == "pick up the red block"


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
