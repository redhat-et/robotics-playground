from __future__ import annotations

from unittest.mock import MagicMock, patch

from fastapi.testclient import TestClient

from robotics_playground.main import app


@patch("robotics_playground.rerun_logger.rr")
def test_websocket_instruction_flow(mock_rr: MagicMock):
    with TestClient(app) as client, client.websocket_connect("/ws/sessions/test") as ws:
        ws.send_json({"type": "instruction", "text": "wave"})
        data = ws.receive_json()
        assert "type" in data


@patch("robotics_playground.rerun_logger.rr")
def test_websocket_connect_and_close(mock_rr: MagicMock):
    with TestClient(app) as client, client.websocket_connect("/ws/sessions/test"):
        pass  # connect and immediately close — should not crash
