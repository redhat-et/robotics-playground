# Phase 3: VLA Policy Integration — Design Spec

## Goal

Connect the Robotics Playground backend to a real VLA policy server (DreamZero on vLLM-Omni) via the OpenPI protocol, enabling end-to-end autonomous robot control from natural language instructions.

**Milestone**: User selects DreamZero, connects to Isaac Sim, types "pick up the red block," watches the robot execute autonomously.

## Architecture

The backend acts as a proxy: incoming camera and proprioception observations from the ROS 2 bridge flow through an EmbodimentAdapter for normalization, then to an OpenPI WebSocket client connecting to vLLM-Omni. Action chunks return through the adapter for denormalization and are published back to Isaac Lab as ROS 2 joint commands.

```text
Isaac Lab (via Zenoh) → Backend ROS2Bridge (rclpy subscriptions)
                              │
                              ├──→ Rerun Logger (log observations)
                              │
                              ▼
                      EmbodimentAdapter.observation_to_openpi()
                        - Resize images to 224×224
                        - Reorder joints URDF → DROID training order
                        - Normalize physical units → [-1, 1]
                        - Remap keys to OpenPI dict format
                              │
                              ▼
                      OpenPIClient.infer() (WebSocket + msgpack)
                              │
                              ▼
                      vLLM-Omni DreamZero → action chunk (10, 8)
                              │
                              ├──→ Rerun Logger Path A: raw tensor (ML debug)
                              │
                              ▼
                      EmbodimentAdapter.action_chunk_from_openpi()
                        - Split 7 arm velocities + 1 gripper position
                        - Denormalize [-1, 1] → physical units
                        - Reorder DROID → URDF order
                        - Build JointState with NaN dispatch
                              │
                              ├──→ Rerun Logger Path B: physical trajectory
                              │
                              ▼
                      ROS2Bridge.send_action() → Zenoh → Isaac Lab
```

### Approach: Monolithic Backend Extension

All new components (OpenPI client, EmbodimentAdapter, lockstep loop) live inside the existing backend process. No sidecar, no separate ROS 2 node.

**Rationale**:

- Single process eliminates IPC overhead and double-subscription bottleneck
- Avoids Python environment clashes between rclpy and VLA toolchains
- Matches Phase 2 architecture — natural extension
- Lockstep loop stays in one place

## Execution Model: Control-Step Lockstep

Isaac Sim cannot run physics at the policy's native 15 Hz — doing so causes physical instability. The system uses synchronous decimated execution.

**Configuration**:

- Physics time step (sim_dt): 150 Hz
- Policy control step (control_dt): 15 Hz
- Decimation factor: 10 physics ticks per control action

**Loop**:

1. Collect observation from Isaac Lab (post-step sensor data)
2. Normalize via EmbodimentAdapter → OpenPI dict
3. Send to vLLM-Omni via OpenPI WebSocket (sim frozen during inference)
4. Receive 10-step action chunk
5. For each of the 10 actions:
   a. Publish joint command via ROS 2
   b. Call `/step_simulation` (advances 10 physics ticks)
   c. Collect observation
6. Repeat from step 2

The virtual world freezes while the policy "thinks." This eliminates gravity drift and ensures deterministic execution for fair policy benchmarking and A/B testing.

## New Components

### PolicyClient Protocol (`policy/protocol.py`)

```python
class PolicyClient(Protocol):
    async def connect(self) -> None: ...
    async def infer(self, obs: dict) -> dict: ...
    async def reset(self) -> None: ...
    async def close(self) -> None: ...
```

`infer()` takes a normalized OpenPI observation dict and returns an action dict. The protocol is transport-agnostic — implementations handle serialization.

### OpenPIClient (`policy/openpi_client.py`)

- WebSocket client connecting to `/v1/realtime/robot/openpi`
- Uses `websockets.sync.client` wrapped in `asyncio.to_thread()` (upstream OpenPI client is synchronous; wrapping avoids blocking the async event loop)
- Serialization: msgpack with numpy support (vendored `msgpack_numpy.py` from `openpi-client`, ~60 lines)
- Persistent connection — opened on `connect()`, kept alive across the session, reconnects on failure
- Configurable endpoint URL

**Observation dict sent to server**:

```python
{
    "observation/exterior_image_1_left": np.ndarray,  # (224, 224, 3) uint8
    "observation/wrist_image_left": np.ndarray,        # (224, 224, 3) uint8
    "observation/joint_position": np.ndarray,          # (7,) float, normalized [-1, 1]
    "observation/gripper_position": np.ndarray,        # (1,) float, normalized [-1, 1]
    "prompt": str,                                     # language instruction
}
```

**Action dict received**:

```python
{"actions": np.ndarray}  # shape (10, 8) — 10-step chunk: 7 joint velocities + 1 gripper
```

### MockClient (`policy/mock_client.py`)

Replaces `mock_policy.py`. Conforms to `PolicyClient` protocol. Returns random `(10, 8)` action chunks with 50ms simulated latency. Used when `policy.type: "mock"`.

### EmbodimentAdapter (`policy/embodiment_adapter.py`)

Pure Python class, no ROS dependency. Configured from YAML with robot-specific parameters.

**Responsibilities**:

1. **Observation normalization** (ROS2 → OpenPI):
   - Resize camera images to 224×224 with padding
   - Reorder joint positions from URDF order to DROID training order via name→index mapping
   - Min-max scale joint positions and gripper from physical units to [-1, 1] using joint limits
   - Remap dict keys: `{wrist: ndarray}` → `{observation/wrist_image_left: ndarray}`

2. **Action denormalization** (OpenPI → ROS2):
   - Split `(10, 8)` chunk into 7 arm joint velocities + 1 gripper position per step
   - Denormalize from [-1, 1] back to physical units
   - Reorder from DROID training order back to URDF order
   - Build `JointState` fields: `velocity[]` for arm joints (NaN positions), `position[]` for gripper (NaN velocity)

**Interface**:

```python
class EmbodimentAdapter:
    def __init__(self, config: EmbodimentConfig): ...
    def observation_to_openpi(self, obs: Observation, instruction: str) -> dict: ...
    def action_chunk_from_openpi(self, raw: dict) -> list[Action]: ...
```

**Configuration** (loaded from `config.yaml`):

```yaml
policy:
  embodiment:
    joint_names: [panda_joint1, ..., panda_joint7]      # URDF order
    training_order: [panda_joint1, ..., panda_joint7]    # DROID order (same for Franka)
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
    image_size: [224, 224]
```

## Modified Components

### Extended Action Type (`bridges/protocol.py`)

```python
class Action(TypedDict):
    joint_positions: list[float]   # NaN for velocity-controlled joints
    joint_velocities: list[float]  # NaN for position-controlled joints
    gripper_position: float        # absolute gripper position
```

Both arrays are in URDF order (EmbodimentAdapter handles reordering). The NaN convention matches Isaac Sim's per-joint mode dispatch: if a joint index has a real value in `velocity[]` and NaN in `position[]`, Isaac Sim applies velocity control for that joint, and vice versa.

### ROS2Bridge Updates (`bridges/ros2_bridge.py`)

**New method** — `get_observation()`:

```python
async def get_observation(self) -> Observation:
    return await self._obs_queue.get()
```

Blocks until the next observation arrives after a sim step. The existing `observation_stream()` stays for backward compatibility — the session selects lockstep mode when `policy.type` is `"openpi"` and reactive mode when `policy.type` is `"mock"` (Phase 2 behavior).

**Updated `send_action()`** — publishes both position and velocity arrays:

```python
msg.position = [float(p) for p in action["joint_positions"]]
msg.velocity = [float(v) for v in action["joint_velocities"]]
```

**Configurable decimation** — `sim_control("step")` uses `config.ros2.physics_decimation` (default 10) instead of hardcoded 1.

**New config field**:

```python
class ROS2Config(BaseModel):
    # ... existing fields ...
    physics_decimation: int = 10
```

**Protocol update** — add `get_observation()` to `RobotBridge`:

```python
class RobotBridge(Protocol):
    async def get_observation(self) -> Observation: ...
    def observation_stream(self) -> AsyncIterator[Observation]: ...
    # ... rest unchanged ...
```

### Lockstep Session Loop (`session.py`)

Replaces the reactive `async for obs in self._bridge.observation_stream()` with an imperative lockstep controller:

1. Pause sim, collect initial observation
2. Wait for play/step (pause/resume logic unchanged)
3. Normalize observation → OpenPI dict via EmbodimentAdapter
4. Log observation to Rerun
5. Call `PolicyClient.infer()` (blocks until vLLM-Omni returns)
6. Log raw action tensor to Rerun (Path A: ML debug)
7. Denormalize action chunk via EmbodimentAdapter
8. Log physical trajectory to Rerun (Path B: 3D intent)
9. Execute 10 actions sequentially: publish → step sim → collect obs → log
10. Repeat from step 2

Pause can interrupt mid-chunk. Session constructor takes `PolicyClient` and `EmbodimentAdapter` in addition to bridge and logger.

### Dual-Path Rerun Logging (`rerun_logger.py`)

**Path A — ML diagnostics** (pre-conversion, raw tensors):

- `{prefix}/policy/raw_output` — `rr.Tensor` of the full (10, 8) array
- `{prefix}/policy/raw_output/dim_{i}` — per-dimension time series
- `{prefix}/policy/inference_ms` — inference latency scalar

**Path B — Physical trajectory** (post-conversion, denormalized):

- `{prefix}/intent/joint_{j}_velocity` — per-joint velocity in physical units
- `{prefix}/intent/gripper` — gripper position in meters

**Updated blueprint**: Adds a "Policy Output" time series panel alongside the existing "Joint States" panel.

### Configuration (`config.py`)

New models:

```python
class EmbodimentConfig(BaseModel):
    joint_names: list[str] = []
    training_order: list[str] = []
    joint_limits: dict[str, list[float]] = {}
    gripper_joint: str = ""
    gripper_limits: list[float] = [0.0, 0.04]
    camera_mapping: dict[str, str] = {}
    image_size: list[int] = [224, 224]

class PolicyConfig(BaseModel):
    type: str = "mock"
    endpoint: str = ""
    model_name: str = "dreamzero"
    embodiment: EmbodimentConfig = EmbodimentConfig()
```

### Wiring (`main.py`)

Factory in lifespan creates `PolicyClient` (OpenPI or Mock) and `EmbodimentAdapter` based on config, passes both to `Session`.

## Dependencies

New pip dependencies in `pyproject.toml`:

```
msgpack >= 1.0
websockets >= 12.0
Pillow >= 10.0
```

Vendored: `msgpack_numpy.py` (~60 lines from `openpi-client`) for numpy↔msgpack serialization.

## Platform Agent Coordination

Changes needed in `redhat-et/physical-ai-platform-demo`:

1. **Isaac Lab USD scene**: Set `stiffness=0, damping>0` for arm joints 1-7 (velocity control), `stiffness>0` for gripper joint (position control)
2. **Backend ConfigMap**: Add `policy` section with OpenPI endpoint and embodiment config
3. **DreamZero InferenceService**: Scale up to `minReplicas: 1` for testing
4. **Backend deployment**: No container/resource changes needed (current 2Gi limit sufficient)

## Deferred (Out of Scope)

- **Dynamic model switching from frontend** — currently the selected model ID is informational; the backend connects to whatever `policy.endpoint` is configured. Dynamic switching deferred to Phase 4 (comparison mode needs two simultaneous policy connections).
- **3D ghost skeleton overlay** — requires forward kinematics (URDF parser). Time-series trajectory view delivers the key insight; 3D extension is future work.
- **Session CRUD REST API** — keep single global session for now.
- **MaaS catalog integration** — model list stays hardcoded; MaaS discovery is Phase 4+.
- **Multi-turn context / vLLM-Omni session management API** — fall back to stateless per-observation instruction injection until the API stabilizes.

## Verification

1. `make lint` — all linters pass
2. `make test` — unit tests for EmbodimentAdapter (normalization round-trip, joint reorder, NaN dispatch), MockClient, session lockstep logic
3. `make build` — container image builds with new dependencies
4. Integration test with mock policy: lockstep loop runs, Rerun shows dual-path logging
5. Platform agent updates ConfigMap + USD scene
6. DreamZero InferenceService scaled up
7. End-to-end: type instruction → policy infers → robot moves in Isaac Sim → camera feeds update in Rerun
