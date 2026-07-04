# Phase 2: ROS 2 Bridge — Design Spec

## Goal

Replace the mock robot bridge with real ROS 2 communication to Isaac Sim. After Phase 2, a user connects the playground to a running Isaac Sim instance, sees real camera feeds and joint state telemetry in the Rerun viewer, and controls the simulation (play/pause/reset/step/speed) from the browser.

## Scope

**In scope:**

- Bridge abstraction layer (`RobotBridge` protocol) with `MockBridge` and `ROS2Bridge` implementations
- `ROS2Bridge`: rclpy node subscribing to camera/joint topics, publishing joint commands, calling sim control services
- Backend container switch from `hi/python:3.14` (distroless) to UBI9 Python with ROS 2 Jazzy
- YAML-based configuration with Pydantic validation (`config.yaml`)
- ConfigMap (Kubernetes) / mounted config file (Podman) for deployment configuration
- Isaac Sim as optional integrated container (Podman profile / Kustomize overlay) or external instance
- Frontend: speed slider, bridge connection status indicator
- Clean observation format (all cameras in `cameras` dict)

**Out of scope (deferred):**

- Manual teleoperation mode
- Scene selector UI
- VLA policy integration (Phase 3)
- Comparison mode (Phase 4)
- Physical robot support (Phase 5)

## Architecture

### Bridge Abstraction

A `RobotBridge` protocol decouples `Session` from the communication mechanism:

```
                  Session
                     │
                     ▼
              ┌─────────────┐
              │ RobotBridge  │  (Protocol)
              │  protocol    │
              └──────┬───────┘
                     │
            ┌────────┴────────┐
            ▼                 ▼
     ┌─────────────┐   ┌──────────────┐
     │ MockBridge   │   │ ROS2Bridge   │
     │              │   │              │
     └─────────────┘   └──────────────┘
                              │
                         rclpy node
                              │
                    ┌─────────┴─────────┐
                    ▼                   ▼
             Isaac Sim           (Future: physical
             ROS 2 bridge         robot ROS 2)
```

### RobotBridge Protocol

```python
class RobotBridge(Protocol):
    async def start(self) -> None: ...
    def observation_stream(self) -> AsyncIterator[Observation]: ...
    async def send_action(self, action: Action) -> None: ...
    async def sim_control(self, action: str, speed: float | None = None) -> None: ...
    async def close(self) -> None: ...
```

### Observation Format

All bridges produce the same observation shape:

```python
Observation = TypedDict("Observation", {
    "step": int,
    "cameras": dict[str, np.ndarray],    # name -> HxWx3 uint8
    "joint_positions": list[float],
    "joint_velocities": list[float],
})
```

`MockBridge` produces one camera (`"wrist"`) with synthetic gradient images.
`ROS2Bridge` produces cameras matching the configured topic map (e.g. `"wrist"`, `"head"`).

### Action Format

```python
Action = TypedDict("Action", {
    "joint_positions": list[float],  # target joint positions
})
```

In Phase 2, the mock policy still generates random actions. `ROS2Bridge.send_action()` translates these into a `trajectory_msgs/JointTrajectory` message. `MockBridge.send_action()` is a no-op (the mock has no actuator to command).

### Session Refactoring

`Session` is updated to:

- Accept a `RobotBridge` instance (injected, not created internally)
- Delegate sim control to `bridge.sim_control()` instead of managing play/pause state internally (Isaac Sim owns that state when using ROS2Bridge)
- Call `bridge.send_action()` after policy prediction (Phase 2 still uses mock policy; real policy is Phase 3)
- Drop Phase 1 workarounds where a cleaner design exists

### RerunLogger Updates

`RerunLogger.log_observation()` takes the full `Observation` dict and iterates `cameras`, logging each under `session/policy_0/camera/{name}`. The old per-argument signature is removed.

## ROS2Bridge Implementation

### Threading Model

```
  asyncio event loop (uvicorn)         rclpy executor thread
  ─────────────────────────────        ──────────────────────
  Session._run_loop()                  ROS2Bridge._node
    │                                    │
    ├── async for obs in bridge ◄────── asyncio.Queue ◄── _on_image_cb()
    │                                                  ◄── _on_joint_state_cb()
    │
    ├── bridge.send_action(action) ──► _node.publish(JointTrajectory)
    │
    └── bridge.sim_control("play") ──► _node.call_service(sim_control)
```

`rclpy` runs its own executor in a background thread. ROS 2 subscription callbacks push data into an `asyncio.Queue` (thread-safe). The async `observation_stream()` yields from this queue.

### Observation Assembly

Camera and joint state messages arrive on separate topics at different rates. The bridge maintains a latest-value buffer for each topic. When any camera frame arrives, it assembles a complete observation from the latest values and pushes it to the queue. This avoids blocking on topic synchronization.

### ROS 2 Topics and Services

| ROS 2 Topic/Service | Message Type | Direction | Bridge Method |
| --------------------- | ------------- | ----------- | --------------- |
| Camera topics (configurable) | `sensor_msgs/msg/Image` | Subscribe | `_on_image_cb` → decode to numpy |
| Joint state topic | `sensor_msgs/msg/JointState` | Subscribe | `_on_joint_state_cb` → extract positions/velocities |
| Joint command topic | `trajectory_msgs/msg/JointTrajectory` | Publish | `send_action()` |
| `/set_simulation_state` | `simulation_interfaces/srv/SetSimulationState` | Call | `sim_control("play"\|"pause"\|"stop")` |
| `/step_simulation` | `simulation_interfaces/srv/StepSimulation` | Call | `sim_control("step")` |

The `simulation_interfaces` package is the [ROS 2 Simulation Interfaces standard](https://github.com/ros-simulation/simulation_interfaces). `SetSimulationState` takes a state enum (`STATE_STOPPED=0`, `STATE_PLAYING=1`, `STATE_PAUSED=2`). `StepSimulation` advances by N frames while paused and blocks until complete.

### Lazy Imports

ROS 2 packages (`rclpy`, `sensor_msgs`, etc.) are imported only when `ROS2Bridge` is instantiated. This ensures the mock path works without rclpy installed (local dev, CI).

## Configuration

### Config File Format

The backend loads configuration from a YAML file with Pydantic validation:

```yaml
server:
  host: "0.0.0.0"
  port: 8000
  log_level: "info"

rerun:
  grpc_port: 9876
  web_port: 9090

bridge:
  type: "mock"  # "mock" or "ros2"

ros2:
  domain_id: 0
  discovery_server: null  # set for external Isaac Sim, e.g. "spark-2:11811"
  cameras:
    wrist: "/camera/wrist/rgb"
    head: "/camera/head/rgb"
  joint_state_topic: "/joint_states"
  joint_command_topic: "/joint_commands"
  sim_control_service: "/sim_control"
```

The config file path is set by `PLAYGROUND_CONFIG` env var (default: `/etc/robotics-playground/config.yaml`). Individual fields can be overridden by env vars using Pydantic's nested delimiter (e.g. `BRIDGE__TYPE=ros2`).

### Config Files Shipped

| File | Purpose |
| ------ | --------- |
| `deploy/config/playground.yaml` | Default mock-mode config |
| `deploy/config/playground-ros2.yaml` | Example config for local Isaac Sim |
| `deploy/config/playground-external.yaml` | Example config pointing to external Isaac Sim (e.g. spark-2) |

## Backend Container

### Base Image Change

The backend switches from `hi/python:3.14` (distroless) to `registry.access.redhat.com/ubi9/python-311` to support ROS 2 Jazzy packages.

Python version moves from 3.14 to 3.11 (ROS 2 Jazzy targets 3.11/3.12 on RHEL 9).

### ROS 2 Dependencies

ROS 2 packages are installed from RPMs in the container image, not via pip:

- `ros-jazzy-rclpy`
- `ros-jazzy-sensor-msgs`
- `ros-jazzy-trajectory-msgs`
- `ros-jazzy-simulation-interfaces`

The `pyproject.toml` does not gain ROS 2 entries — they are system packages.

### Containerfile Structure

```dockerfile
FROM registry.access.redhat.com/ubi9/python-311 AS builder
# Add ROS 2 Jazzy RPM repo
# dnf install ROS 2 packages
# Install Python app dependencies via uv

FROM registry.access.redhat.com/ubi9/python-311
# Copy ROS 2 packages + Python deps from builder
# Copy application code
```

### Development Workflow

- `make dev-backend` works locally in mock mode (no rclpy needed)
- CI tests run in mock mode on GitHub Actions
- ROS 2 integration testing requires the container build

## Frontend Changes

### Speed Slider

Add a speed slider to `SimulationControlPanel` that sends the `speed` parameter with `sim_control` WebSocket messages:

```json
{"type": "sim_control", "action": "play", "speed": 1.5}
```

PatternFly `Slider` component, range 0.1x–5x, default 1x.

### Bridge Connection Status

The `status` WebSocket message gains a `bridge_status` field:

```json
{"type": "status", "state": "running", "step": 42, "bridge_status": "connected"}
```

Values: `"connected"`, `"disconnected"`, `"mock"`.

Displayed as a PatternFly `Label` in `SimulationControlPanel`:

- Green for `connected`
- Red for `disconnected`
- Grey for `mock`

### Multi-Camera

No frontend code change needed. The `RerunLogger` logs multiple cameras as separate entities; the Rerun viewer auto-discovers and displays them.

## Deployment

### Podman Compose

```yaml
services:
  ui:
    image: robotics-playground-ui:${TAG:-local}
    ports: ["8080:8080"]

  backend:
    image: robotics-playground:${TAG:-local}
    ports: ["8000:8000", "9876:9876", "9090:9090"]
    volumes:
      - ./config/playground.yaml:/etc/robotics-playground/config.yaml:ro
    environment:
      PLAYGROUND_CONFIG: /etc/robotics-playground/config.yaml

  isaac-sim:
    image: nvcr.io/nvidia/isaac-sim:4.5.0
    profiles: ["gpu"]
    deploy:
      resources:
        reservations:
          devices:
            - capabilities: [gpu]
```

- `make compose-up` — ui + backend in mock mode
- `make compose-up PROFILE=gpu` — adds Isaac Sim for integrated mode
- External Isaac Sim: use `playground-external.yaml` config pointing to remote host

### Kustomize

- **Base:** backend + ui deployments, ConfigMap with mock-mode config
- **Overlay `gpu`:** adds Isaac Sim deployment, patches ConfigMap for ROS 2 bridge mode
- ConfigMap mounted as `/etc/robotics-playground/config.yaml`

### Isaac Sim Deployment Modes

| Mode | Isaac Sim | ROS 2 Discovery | Use Case |
| ------ | ----------- | ----------------- | ---------- |
| Mock (default) | Not needed | N/A | Local dev, CI |
| Integrated | Container alongside backend | Local DDS (same network) | Full-stack on GPU cluster |
| External | Runs elsewhere (e.g. DGX Spark) | `ROS_DISCOVERY_SERVER` | Dev on MacBook, sim on DGX |

## Testing Strategy

| Level | What | Runs Where |
| ------- | ------ | ----------- |
| Unit tests | MockBridge, ROS2Bridge (mocked rclpy), config parsing, observation assembly | CI (GitHub Actions) |
| Integration (mock) | Full session loop with MockBridge, WebSocket protocol | CI |
| Integration (ROS 2) | Backend container + lightweight ROS 2 test publisher container | Local container build |
| E2E smoke test | Backend + Isaac Sim on spark-2, frontend connected | Manual on spark-2 |

The ROS 2 integration test uses a small test container that publishes synthetic `sensor_msgs/Image` and `sensor_msgs/JointState` on the expected topics, validating `ROS2Bridge` against real ROS 2 without a GPU.

## Phase 2 Milestone

User opens the playground, backend connects to Isaac Sim (local or remote) via ROS 2, sees real camera feeds from the Franka Panda cube-stacking scene and joint state telemetry in the Rerun viewer, and can play/pause/reset/step the simulation at configurable speed from the browser.
