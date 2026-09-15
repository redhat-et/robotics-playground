from __future__ import annotations

import asyncio
import contextlib
import faulthandler
import json
import logging
import os
import threading
from collections.abc import AsyncGenerator
from contextlib import asynccontextmanager

from fastapi import FastAPI, Query, WebSocket, WebSocketDisconnect

from robotics_playground.bridges import create_bridge
from robotics_playground.config import load_config
from robotics_playground.rerun_logger import RerunLogger
from robotics_playground.session import Session

config = load_config()
logging.basicConfig(level=getattr(logging, config.server.log_level.upper(), logging.INFO))
logger = logging.getLogger(__name__)
faulthandler.enable()


class _SimState:
    """Tracks sim physics state based on commands sent."""

    def __init__(self):
        self.state = "idle"

    def on_command(self, action: str) -> None:
        if action == "play":
            self.state = "running"
        elif action == "pause":
            self.state = "paused"
        elif action in ("stop", "reset"):
            self.state = "idle"


async def _observation_streamer(
    bridge,
    rerun_logger: RerunLogger,
    stop_event: asyncio.Event,
):
    """Always-on observation logger.

    Streams observations to Rerun as soon as the bridge is connected,
    independent of the policy session.
    """
    obs_step = [0]
    logging_active = False

    def _log_obs(obs):
        step = obs_step[0]
        obs_step[0] += 1
        rerun_logger.log_observation(obs, step)

    try:
        while not stop_event.is_set():
            bridge_ok = bridge.bridge_status == "connected"

            if bridge_ok and not logging_active:
                bridge.add_observation_listener(_log_obs)
                logging_active = True
                logger.info("Observation streaming started")
            elif not bridge_ok and logging_active:
                bridge.remove_observation_listener(_log_obs)
                logging_active = False
                logger.info("Observation streaming paused (bridge disconnected)")

            await asyncio.sleep(1.0)
    except asyncio.CancelledError:
        pass
    finally:
        if logging_active:
            bridge.remove_observation_listener(_log_obs)

    return _log_obs, obs_step


async def _heartbeat(bridge, session: Session, stop_event: asyncio.Event):
    while not stop_event.is_set():
        try:
            await asyncio.sleep(60)
            logger.info(
                "Heartbeat: event_loop=alive, threads=%d, sim=%s, bridge=%s, policy=%s",
                threading.active_count(),
                session.sim_state,
                bridge.bridge_status,
                session.policy_status,
            )
        except asyncio.CancelledError:
            break
        except Exception:
            logger.exception("Heartbeat error")


def _extract_origin(url: str) -> str:
    from urllib.parse import urlparse

    parsed = urlparse(url)
    if not parsed.scheme or not parsed.hostname:
        return ""
    origin = f"{parsed.scheme}://{parsed.hostname}"
    if parsed.port:
        origin += f":{parsed.port}"
    return origin


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncGenerator[None]:
    rerun_viewer_url = os.environ.get("RERUN_VIEWER_URL", "")
    cors_origin = _extract_origin(rerun_viewer_url) if rerun_viewer_url else ""
    cors_origins = [cors_origin] if cors_origin else None
    rerun_logger = RerunLogger(
        port=config.rerun.grpc_port,
        camera_names=list(config.ros2.cameras.keys()) or None,
        cors_allow_origin=cors_origins,
        recording_dir=config.rerun.recording_dir,
    )
    rerun_logger.start()

    try:
        bridge = create_bridge(config)
        await bridge.start()
        logger.info("Bridge started: %s", bridge.bridge_status)

        sim_state = _SimState()
        session = Session(
            bridge=bridge,
            policy_config=config.policy,
            rerun_logger=rerun_logger,
        )
        await session.start_loop()

        stop_event = asyncio.Event()
        obs_task = asyncio.create_task(_observation_streamer(bridge, rerun_logger, stop_event))
        heartbeat_task = asyncio.create_task(_heartbeat(bridge, session, stop_event))

        app.state.bridge = bridge
        app.state.rerun_logger = rerun_logger
        app.state.session = session
        app.state.sim_state = sim_state
        try:
            yield
        finally:
            await session.shutdown()
            stop_event.set()
            obs_task.cancel()
            heartbeat_task.cancel()
            with contextlib.suppress(asyncio.CancelledError):
                await obs_task
            with contextlib.suppress(asyncio.CancelledError):
                await heartbeat_task
            await bridge.close()
    finally:
        rerun_logger.shutdown()


app = FastAPI(title="Robotics Playground", lifespan=lifespan)


@app.get("/api/health")
def health():
    bridge = getattr(app.state, "bridge", None)
    bridge_status = bridge.bridge_status if bridge else "unknown"
    if bridge and bridge_status != "connected":
        return {"status": "degraded", "bridge": bridge_status}
    return {"status": "ok"}


@app.get("/api/config")
def get_config():
    return {
        "wsUrl": os.environ.get("WS_EXTERNAL_URL", ""),
        "rerunViewerUrl": os.environ.get("RERUN_VIEWER_URL", ""),
        "rerunGrpcUrl": os.environ.get("RERUN_GRPC_URL", ""),
        "rerunAssetsUrl": os.environ.get("RERUN_ASSETS_URL", ""),
    }


@app.get("/api/models")
def list_models(type: str = Query(default="robotics")):
    if config.policy.models:
        models = [
            {"id": model_id, "name": mc.name or model_id, "type": "robotics"}
            for model_id, mc in config.policy.models.items()
        ]
    else:
        models = [{"id": "mock-v1", "name": "Mock", "type": "robotics"}]
    return {"models": [m for m in models if m["type"] == type]}


@app.websocket("/ws/sessions/{session_id}")
async def websocket_session(websocket: WebSocket, session_id: str):
    await websocket.accept()
    session: Session = app.state.session
    sim_state: _SimState = app.state.sim_state
    bridge = app.state.bridge
    rerun_logger: RerunLogger = app.state.rerun_logger
    send_lock = asyncio.Lock()

    async def send_status():
        try:
            while True:
                async with send_lock:
                    await websocket.send_json(
                        {
                            "type": "status",
                            "sim_status": bridge.bridge_status,
                            "sim_state": sim_state.state,
                            "policy_status": session.policy_status,
                            "policy_error": session.policy_error,
                            "model_id": session.model_id,
                            "instruction": session.instruction,
                            "step": session.step,
                        }
                    )
                await asyncio.sleep(1)
        except (WebSocketDisconnect, ConnectionError):
            pass

    send_task = asyncio.create_task(send_status())

    try:
        while True:
            raw = await websocket.receive_text()
            try:
                msg = json.loads(raw)
            except json.JSONDecodeError:
                continue

            msg_type = msg.get("type")

            if msg_type == "instruction":
                text = msg.get("text", "")
                session.set_instruction(text)
                async with send_lock:
                    await websocket.send_json(
                        {"type": "instruction_ack", "status": "received", "text": text}
                    )

            elif msg_type == "clear_instruction":
                session.clear_instruction()
                async with send_lock:
                    await websocket.send_json(
                        {"type": "instruction_ack", "status": "cleared", "text": ""}
                    )

            elif msg_type == "sim_control":
                action = msg.get("action", "")
                speed = msg.get("speed")
                try:
                    await bridge.sim_control(action, speed=speed)
                except Exception:
                    logger.exception("sim_control failed: %s", action)
                else:
                    sim_state.on_command(action)
                    session.sim_state = sim_state.state
                    if action == "reset":
                        rerun_logger.clear()
                        session.clear_instruction()

            elif msg_type == "select_model":
                model_id = msg.get("model_id", "")
                await session.select_model(model_id)

    except WebSocketDisconnect:
        pass
    finally:
        send_task.cancel()
        with contextlib.suppress(asyncio.CancelledError):
            await send_task
