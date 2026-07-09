from __future__ import annotations

import asyncio
import contextlib
import json
import os
from collections.abc import AsyncGenerator
from contextlib import asynccontextmanager

from fastapi import FastAPI, Query, WebSocket, WebSocketDisconnect

from robotics_playground.bridges import create_bridge
from robotics_playground.config import load_config
from robotics_playground.rerun_logger import RerunLogger
from robotics_playground.session import Session

config = load_config()


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncGenerator[None]:
    logger = RerunLogger(
        port=config.rerun.grpc_port,
        web_port=config.rerun.web_port,
        camera_names=list(config.ros2.cameras.keys()) or None,
    )
    logger.start()
    bridge = create_bridge(config)
    session = Session(bridge=bridge, rerun_logger=logger)
    app.state.rerun_logger = logger
    app.state.session = session
    try:
        yield
    finally:
        await session.stop()


app = FastAPI(title="Robotics Playground", lifespan=lifespan)

MODELS = [
    {"id": "dreamzero-v1", "name": "DreamZero", "type": "robotics"},
]


@app.get("/api/health")
def health():
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
