# Per-Model Configuration and Dynamic Model Switching — Design Spec

## Goal

Enable the Robotics Playground to support multiple VLA policy models (DreamZero on vLLM-Omni, pi0.5 on native OpenPI) with per-model configuration and frontend-driven model selection.

**Milestone**: User selects pi0.5 from the policy dropdown, presses Play, and the backend connects to the pi0.5 inference server with the correct endpoint, action horizon, and camera mapping — without restarting.

## Constraints

- Model switching only while the session is idle (before pressing Play)
- Per-model config lives in the backend `config.yaml` (ConfigMap) — no auto-discovery yet
- Both models target the same Franka robot — shared embodiment config (joints, limits, training order)
- Image resizing removed — servers handle their own resizing; raw camera frames sent as-is
- Builds on the `feat-pi05-wire-format` branch which already provides dual msgpack wire format support and the pi0.5 model catalog entry

## Architecture

```text
Frontend (PolicyBar)              Backend (FastAPI)
┌──────────────────┐              ┌────────────────────────────────┐
│ Model dropdown   │──select_model──▶ Session.select_model(id)    │
│ [DreamZero ▾]    │   (WebSocket)   │  (idle only)               │
│                  │                 │                              │
│ [▶ Play]  ───────│──sim_control───▶ Session.start()              │
│                  │                 │  ├─ look up ModelConfig      │
│                  │                 │  ├─ create OpenPIClient(ep)  │
│                  │                 │  ├─ rebuild EmbodimentAdapter│
│                  │                 │  └─ connect + run loop       │
│                  │◀──status───────│  {model_id: "pi05-v1", ...}  │
└──────────────────┘              └────────────────────────────────┘

config.yaml:
  policy.models:
    dreamzero-v1: {endpoint, action_horizon}
    pi05-v1:      {endpoint, action_horizon}
  policy.embodiment: {joints, limits, cameras}  ← shared
```

## Config Model

### New: `ModelConfig`

Per-model settings that differ between DreamZero and pi0.5:

```python
class ModelConfig(BaseModel):
    name: str = ""
    endpoint: str
    action_horizon: int = Field(default=4, gt=0)
    camera_mapping: dict[str, str] | None = None
```

- `name`: human-readable display name for the frontend (e.g. "DreamZero", "pi0.5")
- `endpoint`: WebSocket URL for the model's inference server
- `action_horizon`: how many actions from the chunk to execute before re-inferring
- `camera_mapping`: optional override of the shared embodiment camera mapping; if `None`, the shared `embodiment.camera_mapping` is used

### Modified: `PolicyConfig`

```python
class PolicyConfig(BaseModel):
    type: str = "mock"
    default_model: str = ""
    models: dict[str, ModelConfig] = {}
    embodiment: EmbodimentConfig = EmbodimentConfig()
```

Removed fields:

- `endpoint` — replaced by per-model `ModelConfig.endpoint`
- `model_name` — replaced by `default_model` (references a key in `models`)
- `action_horizon` — moved to `ModelConfig`

### Modified: `EmbodimentConfig`

The `image_size` field is removed. Servers handle their own image resizing. The `camera_mapping` field remains as the shared default.

### Config YAML Example

```yaml
policy:
  type: openpi
  default_model: dreamzero-v1
  models:
    dreamzero-v1:
      name: DreamZero
      endpoint: "ws://dreamzero-predictor/v1/realtime/robot/openpi"
      action_horizon: 4
    pi05-v1:
      name: "pi0.5"
      endpoint: "ws://pi05-predictor/"
      action_horizon: 8
  embodiment:
    joint_names: [panda_joint1, panda_joint2, panda_joint3, panda_joint4, panda_joint5, panda_joint6, panda_joint7]
    training_order: [panda_joint1, panda_joint2, panda_joint3, panda_joint4, panda_joint5, panda_joint6, panda_joint7]
    joint_limits:
      panda_joint1: [-2.8973, 2.8973]
      panda_joint2: [-1.7628, 1.7628]
      panda_joint3: [-2.8973, 2.8973]
      panda_joint4: [-3.0718, -0.0698]
      panda_joint5: [-2.8973, 2.8973]
      panda_joint6: [-0.0175, 3.7525]
      panda_joint7: [-2.8973, 2.8973]
    gripper_joint: panda_finger_joint1
    gripper_limits: [0.0, 0.04]
    camera_mapping:
      wrist: "observation/wrist_image_left"
      exterior_1: "observation/exterior_image_1_left"
      exterior_2: "observation/exterior_image_2_left"
```

## Frontend Changes

### `PolicyBar`

Currently stores `selectedPolicy` as local React state. Changes:

- Accept `onSelectModel: (modelId: string) => void` and `selectedModel: string` as props (lift state up)
- Accept `disabled: boolean` prop — set to `true` when session is not idle
- Remove internal `selectedPolicy` state

### `RoboticsPlayground`

- Hold `selectedModel` state, initialized from the first model in the `/api/models` response
- Pass `selectedModel` and `setSelectedModel` down to `PolicyBar`
- Pass `selectedModel` to `useSession`

### `useSession`

- Accept `modelId` parameter
- Send `{type: "select_model", model_id}` over WebSocket when `modelId` changes
- Add `model_id` to the `SessionState` interface, populated from the status message

### `/api/models` Endpoint

Replace the hardcoded `MODELS` list. Derive from `config.policy.models`:

```python
@app.get("/api/models")
def list_models(type: str = Query(default="robotics")):
    models = [
        {"id": model_id, "name": mc.name or model_id, "type": "robotics"}
        for model_id, mc in config.policy.models.items()
    ]
    return {"models": models}
```

When `policy.type` is `"mock"` and no models are configured, return a single mock entry.

## Backend Session Changes

### `Session.__init__`

Replace pre-built `policy` and fixed `action_horizon` parameters with the full `PolicyConfig`:

```python
def __init__(
    self,
    bridge: RobotBridge,
    policy_config: PolicyConfig,
    rerun_logger: RerunLogger,
):
```

The session holds `policy_config` and creates the `OpenPIClient` and `EmbodimentAdapter` on demand at `start()` time.

### `Session.select_model(model_id)`

Stores the selected model ID. Validates against `policy_config.models` keys. Only works while `state == "idle"`. Raises `ValueError` for unknown model IDs.

### `Session.start()`

On play:

1. Look up `ModelConfig` for the selected model ID
2. Resolve camera mapping: model-specific override or shared `embodiment.camera_mapping`
3. Create `EmbodimentAdapter` with the resolved config (lightweight, no cost to rebuilding)
4. Create `OpenPIClient(model_config.endpoint)` — or `MockClient()` if `policy.type == "mock"` (mock mode ignores the models dict entirely and uses MockClient with default action_horizon)
5. Connect and start the run loop with the model's `action_horizon`

### `Session.stop()`

Closes the policy client as before. The adapter and client references can be cleared.

### Status Message

Add `model_id` to the periodic status broadcast:

```python
{
    "type": "status",
    "state": session.state,
    "step": session.step,
    "instruction": session.instruction,
    "bridge_status": session.bridge_status,
    "model_id": session.model_id,
}
```

### WebSocket Handler

Add `select_model` message type:

```python
elif msg_type == "select_model":
    model_id = msg.get("model_id", "")
    try:
        session.select_model(model_id)
    except ValueError:
        pass  # ignore invalid model IDs
```

## `main.py` Lifespan Changes

The lifespan no longer creates the policy client or adapter — the session does that on `start()`. Simplified to:

```python
session = Session(
    bridge=bridge,
    policy_config=config.policy,
    rerun_logger=rerun_logger,
)
```

The `create_policy()` factory in `policy/__init__.py` moves inside the session or is replaced by direct `OpenPIClient` construction. The factory may be kept for the mock/openpi type dispatch.

## EmbodimentAdapter Changes

- Remove `image_size` from constructor / config
- Remove `_resize_image()` method
- Remove `Pillow` import
- `camera_mapping` remains on `EmbodimentConfig` as the shared default; the adapter accepts an optional override at construction time
- Constructor signature: `EmbodimentAdapter(config: EmbodimentConfig, camera_mapping_override: dict[str, str] | None = None)`

## Removals

| Item | Reason |
| ------ | -------- |
| `EmbodimentConfig.image_size` | Servers resize internally |
| `EmbodimentAdapter._resize_image()` | No longer needed |
| `Pillow` dependency | Only used for image resizing |
| `PolicyConfig.endpoint` | Replaced by per-model endpoints |
| `PolicyConfig.model_name` | Replaced by `default_model` |
| `PolicyConfig.action_horizon` | Moved to `ModelConfig` |
| Hardcoded `MODELS` list in `main.py` | Derived from config |

## Deferred

- **MaaS auto-discovery**: populate `models` dict from ExternalModel CRDs or MaaS catalog at startup. The config shape is ready for this — `models` dict can be filled programmatically instead of from YAML.
- **Per-model embodiment override**: if a future model targets a different robot, `ModelConfig` could carry a full `EmbodimentConfig`. For now, both models target Franka, so shared config suffices.
- **Hot-swap mid-session**: currently idle-only. Comparison mode (Phase 4) will need two simultaneous policy connections.

## Verification

1. `make lint` — all linters pass
2. `make test` — unit tests for new config model, session model switching, WebSocket select_model message, frontend model selection
3. `make build` — container images build (Pillow dependency removed)
4. Integration test: select pi0.5 → press Play → verify OpenPIClient connects to pi0.5 endpoint with correct action_horizon
5. Integration test: select DreamZero → press Play → verify connection to vLLM-Omni endpoint
6. Frontend test: dropdown disabled while session is running
