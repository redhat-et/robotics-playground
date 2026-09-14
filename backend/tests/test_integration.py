"""Integration tests for the backend.

Tests exercise the full FastAPI stack (health endpoint, WebSocket handler,
Session, Bridge) using MockBridge with disconnect/reconnect simulation.
"""

from __future__ import annotations

from unittest.mock import MagicMock, patch

from fastapi.testclient import TestClient

from robotics_playground.main import app

_MAX_RECV = 20


def _receive_status(ws, max_recv: int = _MAX_RECV):
    """Receive up to *max_recv* messages, returning the first status message."""
    for _ in range(max_recv):
        data = ws.receive_json()
        if data.get("type") == "status":
            return data
    raise TimeoutError("No status message received")


@patch("robotics_playground.rerun_logger.rr")
def test_boot_connects_bridge(mock_rr: MagicMock):
    with TestClient(app) as client:
        resp = client.get("/api/health")
        assert resp.status_code == 200
        assert resp.json()["status"] == "ok"

        with client.websocket_connect("/ws/sessions/test") as ws:
            status = _receive_status(ws)
            assert status["sim_status"] == "connected"
            assert status["sim_state"] == "idle"


@patch("robotics_playground.rerun_logger.rr")
def test_health_reports_degraded_when_bridge_disconnected(mock_rr: MagicMock):
    with TestClient(app) as client:
        bridge = app.state.bridge
        bridge.simulate_disconnect()
        try:
            resp = client.get("/api/health")
            assert resp.status_code == 200
            data = resp.json()
            assert data["status"] == "degraded"
            assert data["bridge"] == "disconnected"
        finally:
            bridge.simulate_reconnect()


@patch("robotics_playground.rerun_logger.rr")
def test_bridge_disconnect_reflected_in_ws_status(mock_rr: MagicMock):
    with TestClient(app) as client:
        bridge = app.state.bridge
        with client.websocket_connect("/ws/sessions/test") as ws:
            status = _receive_status(ws)
            assert status["sim_status"] == "connected"

            bridge.simulate_disconnect()
            status = _receive_status(ws)
            assert status["sim_status"] == "disconnected"

            bridge.simulate_reconnect()
            status = _receive_status(ws)
            assert status["sim_status"] == "connected"


@patch("robotics_playground.rerun_logger.rr")
def test_sim_control_play_stop(mock_rr: MagicMock):
    with TestClient(app) as client, client.websocket_connect("/ws/sessions/test") as ws:
        _ = _receive_status(ws)

        ws.send_json({"type": "sim_control", "action": "play"})
        for _ in range(10):
            status = _receive_status(ws)
            if status["sim_state"] == "running":
                break
        assert status["sim_state"] == "running"

        ws.send_json({"type": "sim_control", "action": "stop"})
        for _ in range(10):
            status = _receive_status(ws)
            if status["sim_state"] == "idle":
                break
        assert status["sim_state"] == "idle"
        assert status["sim_status"] == "connected"


@patch("robotics_playground.rerun_logger.rr")
def test_reset_sends_teleport_and_clears(mock_rr: MagicMock):
    with TestClient(app) as client, client.websocket_connect("/ws/sessions/test") as ws:
        _ = _receive_status(ws)

        ws.send_json({"type": "instruction", "text": "pick up red cube"})
        for _ in range(10):
            data = ws.receive_json()
            if data.get("type") == "instruction_ack":
                break

        ws.send_json({"type": "sim_control", "action": "play"})
        for _ in range(10):
            status = _receive_status(ws)
            if status["sim_state"] == "running":
                break

        ws.send_json({"type": "sim_control", "action": "reset"})
        for _ in range(10):
            status = _receive_status(ws)
            if status["sim_state"] == "idle":
                break
        assert status["sim_state"] == "idle"
        assert status["instruction"] == ""
        assert status["sim_status"] == "connected"

        bridge = app.state.bridge
        assert ("reset", None) in bridge.sim_control_calls


@patch("robotics_playground.rerun_logger.rr")
def test_reset_from_idle(mock_rr: MagicMock):
    with TestClient(app) as client, client.websocket_connect("/ws/sessions/test") as ws:
        status = _receive_status(ws)
        assert status["sim_state"] == "idle"

        ws.send_json({"type": "sim_control", "action": "reset"})
        status = _receive_status(ws)
        assert status["sim_state"] == "idle"
        assert status["sim_status"] == "connected"

        bridge = app.state.bridge
        assert ("reset", None) in bridge.sim_control_calls


@patch("robotics_playground.rerun_logger.rr")
def test_sim_control_play_pause_resume_stop(mock_rr: MagicMock):
    with TestClient(app) as client, client.websocket_connect("/ws/sessions/test") as ws:
        _ = _receive_status(ws)

        ws.send_json({"type": "sim_control", "action": "play"})
        for _ in range(10):
            status = _receive_status(ws)
            if status["sim_state"] == "running":
                break
        assert status["sim_state"] == "running"

        ws.send_json({"type": "sim_control", "action": "pause"})
        for _ in range(10):
            status = _receive_status(ws)
            if status["sim_state"] == "paused":
                break
        assert status["sim_state"] == "paused"

        ws.send_json({"type": "sim_control", "action": "play"})
        for _ in range(10):
            status = _receive_status(ws)
            if status["sim_state"] == "running":
                break
        assert status["sim_state"] == "running"

        ws.send_json({"type": "sim_control", "action": "stop"})
        for _ in range(10):
            status = _receive_status(ws)
            if status["sim_state"] == "idle":
                break
        assert status["sim_state"] == "idle"
