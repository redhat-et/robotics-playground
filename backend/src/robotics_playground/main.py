from fastapi import FastAPI, Query

app = FastAPI(title="Robotics Playground")

MODELS = [
    {"id": "dreamzero-v1", "name": "DreamZero", "type": "robotics"},
]


@app.get("/api/health")
def health():
    return {"status": "ok"}


@app.get("/api/models")
def list_models(type: str = Query(default="robotics")):
    return {"models": [m for m in MODELS if m["type"] == type]}
