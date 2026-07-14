from __future__ import annotations

import asyncio
import contextlib
import json
import logging
import os
from collections.abc import AsyncGenerator
from contextlib import asynccontextmanager

from fastapi import FastAPI, Query, WebSocket, WebSocketDisconnect

from robotics_playground.bridges import create_bridge
from robotics_playground.config import load_config
from robotics_playground.policy import create_policy
from robotics_playground.policy.embodiment_adapter import EmbodimentAdapter
from robotics_playground.rerun_logger import RerunLogger
from robotics_playground.session import Session

config = load_config()
logging.basicConfig(level=getattr(logging, config.server.log_level.upper(), logging.INFO))
logger = logging.getLogger(__name__)


async def _observation_logger(
    bridge,
    session: Session,
    rerun_logger: RerunLogger,
    stop_event: asyncio.Event,
):
    """Preview-mode observation logger.

    When the session is idle, steps the sim to render camera frames and logs
    them to Rerun (~2 FPS).  When the session is running, the run loop owns
    observation consumption, so this task yields.
    """
    step = 0
    was_active = False
    while not stop_event.is_set():
        try:
            if bridge.bridge_status not in ("connected", "connecting"):
                await asyncio.sleep(0.5)
                continue

            if session.state in ("running", "paused"):
                was_active = True
                await asyncio.sleep(1.0)
                continue

            if was_active:
                rerun_logger.clear()
                step = 0
                was_active = False

            await bridge.sim_control("step")
            obs = await asyncio.wait_for(bridge.get_observation(), timeout=2.0)
            rerun_logger.log_observation(obs, step)
            step += 1
            await asyncio.sleep(0.5)
        except TimeoutError:
            continue
        except asyncio.CancelledError:
            break
        except Exception:
            logger.exception("Observation logger error")
            await asyncio.sleep(1.0)


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncGenerator[None]:
    rerun_viewer_url = os.environ.get("RERUN_VIEWER_URL", "")
    cors_origins = [rerun_viewer_url] if rerun_viewer_url else None
    rerun_logger = RerunLogger(
        port=config.rerun.grpc_port,
        web_port=config.rerun.web_port,
        camera_names=list(config.ros2.cameras.keys()) or None,
        cors_allow_origin=cors_origins,
    )
    rerun_logger.start()

    try:
        bridge = create_bridge(config)
        await bridge.start()
        logger.info("Bridge started: %s", bridge.bridge_status)

        policy = create_policy(config)
        adapter = EmbodimentAdapter(config.policy.embodiment)
        session = Session(
            bridge=bridge,
            policy=policy,
            adapter=adapter,
            rerun_logger=rerun_logger,
            action_horizon=config.policy.action_horizon,
        )

        stop_logger = asyncio.Event()
        obs_logger_task = asyncio.create_task(
            _observation_logger(bridge, session, rerun_logger, stop_logger)
        )

        app.state.bridge = bridge
        app.state.rerun_logger = rerun_logger
        app.state.session = session
        try:
            yield
        finally:
            await session.stop()
            stop_logger.set()
            obs_logger_task.cancel()
            with contextlib.suppress(asyncio.CancelledError):
                await obs_logger_task
            await bridge.close()
    finally:
        rerun_logger.shutdown()


app = FastAPI(title="Robotics Playground", lifespan=lifespan)

MODELS = [
    {"id": "dreamzero-v1", "name": "DreamZero", "type": "robotics"},
]


@app.get("/api/health")
def health():
    bridge = getattr(app.state, "bridge", None)
    if bridge and bridge.bridge_status != "connected":
        return {"status": "degraded", "bridge": bridge.bridge_status}
    return {"status": "ok"}


@app.get("/api/config")
def get_config():
    return {
        "wsUrl": os.environ.get("WS_EXTERNAL_URL", ""),
        "rerunViewerUrl": os.environ.get("RERUN_VIEWER_URL", ""),
        "rerunGrpcUrl": os.environ.get("RERUN_GRPC_URL", ""),
    }


@app.get("/api/models")
def list_models(type: str = Query(default="robotics")):
    return {"models": [m for m in MODELS if m["type"] == type]}


@app.websocket("/ws/sessions/{session_id}")
async def websocket_session(websocket: WebSocket, session_id: str):
    await websocket.accept()
    session: Session = app.state.session
    send_lock = asyncio.Lock()

    async def send_status():
        try:
            while True:
                async with send_lock:
                    await websocket.send_json(
                        {
                            "type": "status",
                            "state": session.state,
                            "step": session.step,
                            "instruction": session.instruction,
                            "bridge_status": session.bridge_status,
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
                session.send_instruction(text)
                async with send_lock:
                    await websocket.send_json(
                        {"type": "instruction_ack", "status": "received", "text": text}
                    )

            elif msg_type == "sim_control":
                action = msg.get("action", "")
                speed = msg.get("speed")
                await session.handle_sim_control(action, speed=speed)
    except WebSocketDisconnect:
        pass
    finally:
        send_task.cancel()
        with contextlib.suppress(asyncio.CancelledError):
            await send_task
