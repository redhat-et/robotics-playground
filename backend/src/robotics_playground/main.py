from __future__ import annotations

import asyncio
import contextlib
import json
from collections.abc import AsyncGenerator
from contextlib import asynccontextmanager

from fastapi import FastAPI, Query, WebSocket, WebSocketDisconnect

from robotics_playground.config import settings
from robotics_playground.rerun_logger import RerunLogger
from robotics_playground.session import Session


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncGenerator[None]:
    # Startup
    logger = RerunLogger(port=settings.rerun_grpc_port)
    logger.start()
    session = Session(rerun_logger=logger)
    app.state.rerun_logger = logger
    app.state.session = session
    yield
    # Shutdown
    await session.stop()


app = FastAPI(title="Robotics Playground", lifespan=lifespan)

MODELS = [
    {"id": "dreamzero-v1", "name": "DreamZero", "type": "robotics"},
]


@app.get("/api/health")
def health():
    return {"status": "ok"}


@app.get("/api/models")
def list_models(type: str = Query(default="robotics")):
    return {"models": [m for m in MODELS if m["type"] == type]}


@app.websocket("/ws/sessions/{session_id}")
async def websocket_session(websocket: WebSocket, session_id: str):
    await websocket.accept()
    session: Session = app.state.session

    async def send_status():
        try:
            while True:
                await websocket.send_json(
                    {
                        "type": "status",
                        "state": session.state,
                        "step": session.step,
                        "instruction": session.instruction,
                    }
                )
                await asyncio.sleep(1)
        except (WebSocketDisconnect, Exception):
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
                await websocket.send_json(
                    {"type": "instruction_ack", "status": "received", "text": text}
                )

            elif msg_type == "sim_control":
                action = msg.get("action", "")
                await session.handle_sim_control(action)
    except WebSocketDisconnect:
        pass
    finally:
        send_task.cancel()
        with contextlib.suppress(asyncio.CancelledError):
            await send_task
