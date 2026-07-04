# Phase 2: ROS 2 Bridge Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Replace the mock robot bridge with a ROS 2 bridge to Isaac Sim, adding YAML-based configuration, bridge status in the frontend, and updated deployment manifests.

**Architecture:** A `RobotBridge` protocol decouples `Session` from the communication backend. `MockBridge` wraps existing mock logic; `ROS2Bridge` uses rclpy to subscribe to Isaac Sim camera/joint topics and call simulation control services. Configuration is loaded from a YAML file (mounted as ConfigMap in K8s, bind-mounted in Podman).

**Tech Stack:** Python 3.12 (UBI9), rclpy (ROS 2 Jazzy), Pydantic, FastAPI, React 18, PatternFly 6

## Global Constraints

- Conventional Commits for all commit messages
- Run `make lint`, `make test`, `make build` before committing
- Tests first: write tests before implementation
- `deploy/compose.yaml` must not contain `build:` directives
- ROS 2 packages come from system RPMs, not pip
- `rclpy` is lazily imported — mock mode must work without it installed
- Python `requires-python = ">=3.12"` in pyproject.toml (stays as-is; the container uses 3.12 on UBI9)

## File Map

### New files

| File | Responsibility |
| ------ | --------------- |
| `backend/src/robotics_playground/bridges/__init__.py` | Package init, re-exports `RobotBridge`, `MockBridge`, `create_bridge` |
| `backend/src/robotics_playground/bridges/protocol.py` | `RobotBridge` protocol, `Observation`/`Action` type definitions |
| `backend/src/robotics_playground/bridges/mock_bridge.py` | `MockBridge` implementation (wraps existing mock logic) |
| `backend/src/robotics_playground/bridges/ros2_bridge.py` | `ROS2Bridge` implementation (rclpy node) |
| `backend/tests/test_bridges.py` | Tests for MockBridge, protocol conformance |
| `backend/tests/test_ros2_bridge.py` | Tests for ROS2Bridge with mocked rclpy |
| `backend/tests/test_config.py` | Tests for YAML config loading |
| `deploy/config/playground.yaml` | Default mock-mode config file |
| `deploy/config/playground-ros2.yaml` | Example ROS 2 config (local Isaac Sim) |
| `deploy/config/playground-external.yaml` | Example config for external Isaac Sim |
| `deploy/kustomize/config/playground.yaml` | Default config for K8s ConfigMap |
| `deploy/kustomize/configmap.yaml` | ConfigMap resource |

### Modified files

| File | Changes |
| ------ | --------- |
| `backend/src/robotics_playground/config.py` | Replace flat Settings with YAML-based nested config (server, rerun, bridge, ros2 sections) |
| `backend/src/robotics_playground/session.py` | Accept `RobotBridge` instead of hardcoded mocks; delegate sim control to bridge |
| `backend/src/robotics_playground/rerun_logger.py` | Change `log_observation` to accept full `Observation` dict; iterate `cameras` dict |
| `backend/src/robotics_playground/main.py` | Load YAML config, create bridge based on config, pass to Session; add `bridge_status` to WebSocket status; handle `speed` in sim_control |
| `backend/pyproject.toml` | Add `pyyaml` dependency |
| `backend/Containerfile` | Switch to UBI9 base, install ROS 2 Jazzy RPMs |
| `backend/tests/test_session.py` | Update to use MockBridge instead of hardcoded mocks |
| `backend/tests/test_rerun_logger.py` | Update for new `log_observation` signature |
| `backend/tests/test_websocket.py` | Update for `bridge_status` in status messages and `speed` in sim_control |
| `frontend/src/hooks/useSession.ts` | Add `bridgeStatus` to `SessionState`; add `speed` param to `sendSimControl` |
| `frontend/src/components/SimulationControlPanel.tsx` | Add speed slider and bridge status indicator |
| `frontend/test/SimulationControlPanel.test.tsx` | Add tests for speed slider and bridge status |
| `frontend/test/useSession.test.ts` | Update for `bridgeStatus` field |
| `deploy/compose.yaml` | Add config volume mount to backend; add Isaac Sim service with gpu profile |
| `deploy/kustomize/kustomization.yaml` | Add configmap.yaml to resources |
| `deploy/kustomize/backend-deployment.yaml` | Add ConfigMap volume mount, env var |
| `Makefile` | Update compose-up for profile support |

---

### Task 1: YAML Configuration System

**Files:**

- Modify: `backend/src/robotics_playground/config.py`
- Modify: `backend/pyproject.toml`
- Create: `backend/tests/test_config.py`
- Create: `deploy/config/playground.yaml`
- Create: `deploy/config/playground-ros2.yaml`
- Create: `deploy/config/playground-external.yaml`

**Interfaces:**

- Produces: `load_config(path: str | None = None) -> PlaygroundConfig` function, `PlaygroundConfig` model with `.server`, `.rerun`, `.bridge`, `.ros2` sections

- [ ] **Step 1: Write config tests**

Create `backend/tests/test_config.py`:

```python
from __future__ import annotations

import os
import textwrap

import pytest


def test_default_config_loads():
    from robotics_playground.config import PlaygroundConfig

    config = PlaygroundConfig()
    assert config.server.host == "0.0.0.0"
    assert config.server.port == 8000
    assert config.bridge.type == "mock"
    assert config.rerun.grpc_port == 9876


def test_load_config_from_yaml(tmp_path):
    from robotics_playground.config import load_config

    config_file = tmp_path / "config.yaml"
    config_file.write_text(
        textwrap.dedent("""\
            server:
              port: 9000
              log_level: debug
            bridge:
              type: ros2
            ros2:
              domain_id: 5
              cameras:
                wrist: /cam/wrist
        """)
    )
    config = load_config(str(config_file))
    assert config.server.port == 9000
    assert config.server.log_level == "debug"
    assert config.bridge.type == "ros2"
    assert config.ros2.domain_id == 5
    assert config.ros2.cameras == {"wrist": "/cam/wrist"}


def test_load_config_missing_file_returns_defaults():
    from robotics_playground.config import load_config

    config = load_config("/nonexistent/path.yaml")
    assert config.server.port == 8000
    assert config.bridge.type == "mock"


def test_env_var_sets_config_path(tmp_path, monkeypatch):
    from robotics_playground.config import load_config

    config_file = tmp_path / "env.yaml"
    config_file.write_text("server:\n  port: 7777\n")
    monkeypatch.setenv("PLAYGROUND_CONFIG", str(config_file))
    config = load_config()
    assert config.server.port == 7777


def test_ros2_config_defaults():
    from robotics_playground.config import PlaygroundConfig

    config = PlaygroundConfig()
    assert config.ros2.domain_id == 0
    assert config.ros2.discovery_server is None
    assert config.ros2.cameras == {}
    assert config.ros2.joint_state_topic == "/joint_states"
    assert config.ros2.joint_command_topic == "/joint_commands"
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `cd backend && uv run pytest tests/test_config.py -v`
Expected: FAIL — `PlaygroundConfig` and `load_config` don't exist yet

- [ ] **Step 3: Add pyyaml dependency**

Add `pyyaml` to `backend/pyproject.toml` dependencies:

```toml
dependencies = [
    "fastapi>=0.115.0",
    "uvicorn[standard]>=0.34.0",
    "pydantic-settings>=2.7.0",
    "pyyaml>=6.0",
    "rerun-sdk>=0.22.0",
    "numpy>=1.26.0",
]
```

- [ ] **Step 4: Implement config module**

Replace `backend/src/robotics_playground/config.py`:

```python
from __future__ import annotations

import os
from pathlib import Path

import yaml
from pydantic import BaseModel


class ServerConfig(BaseModel):
    host: str = "0.0.0.0"
    port: int = 8000
    log_level: str = "info"


class RerunConfig(BaseModel):
    grpc_port: int = 9876
    web_port: int = 9090


class BridgeConfig(BaseModel):
    type: str = "mock"


class ROS2Config(BaseModel):
    domain_id: int = 0
    discovery_server: str | None = None
    cameras: dict[str, str] = {}
    joint_state_topic: str = "/joint_states"
    joint_command_topic: str = "/joint_commands"
    sim_control_service: str = "/sim_control"


class PlaygroundConfig(BaseModel):
    server: ServerConfig = ServerConfig()
    rerun: RerunConfig = RerunConfig()
    bridge: BridgeConfig = BridgeConfig()
    ros2: ROS2Config = ROS2Config()


def load_config(path: str | None = None) -> PlaygroundConfig:
    if path is None:
        path = os.environ.get("PLAYGROUND_CONFIG")
    if path and Path(path).is_file():
        with open(path) as f:
            data = yaml.safe_load(f) or {}
        return PlaygroundConfig(**data)
    return PlaygroundConfig()
```

- [ ] **Step 5: Run tests to verify they pass**

Run: `cd backend && uv run pytest tests/test_config.py -v`
Expected: All 5 tests PASS

- [ ] **Step 6: Create deploy config files**

Create `deploy/config/playground.yaml`:

```yaml
server:
  host: "0.0.0.0"
  port: 8000
  log_level: "info"

rerun:
  grpc_port: 9876
  web_port: 9090

bridge:
  type: "mock"
```

Create `deploy/config/playground-ros2.yaml`:

```yaml
server:
  host: "0.0.0.0"
  port: 8000
  log_level: "info"

rerun:
  grpc_port: 9876
  web_port: 9090

bridge:
  type: "ros2"

ros2:
  domain_id: 0
  cameras:
    wrist: "/camera/wrist/rgb"
    head: "/camera/head/rgb"
  joint_state_topic: "/joint_states"
  joint_command_topic: "/joint_commands"
  sim_control_service: "/sim_control"
```

Create `deploy/config/playground-external.yaml`:

```yaml
server:
  host: "0.0.0.0"
  port: 8000
  log_level: "info"

rerun:
  grpc_port: 9876
  web_port: 9090

bridge:
  type: "ros2"

ros2:
  domain_id: 0
  discovery_server: "spark-2:11811"
  cameras:
    wrist: "/camera/wrist/rgb"
    head: "/camera/head/rgb"
  joint_state_topic: "/joint_states"
  joint_command_topic: "/joint_commands"
  sim_control_service: "/sim_control"
```

- [ ] **Step 7: Run full test suite and lint**

Run: `cd backend && uv run pytest -v && uv run ruff check src/ tests/ && uv run ruff format --check src/ tests/`
Expected: All pass

- [ ] **Step 8: Commit**

```bash
git add backend/src/robotics_playground/config.py backend/tests/test_config.py backend/pyproject.toml deploy/config/
git commit -m "feat: add YAML-based configuration system with Pydantic validation"
```

---

### Task 2: Bridge Protocol and MockBridge

**Files:**

- Create: `backend/src/robotics_playground/bridges/__init__.py`
- Create: `backend/src/robotics_playground/bridges/protocol.py`
- Create: `backend/src/robotics_playground/bridges/mock_bridge.py`
- Create: `backend/tests/test_bridges.py`

**Interfaces:**

- Consumes: nothing (standalone types)
- Produces:
  - `Observation = TypedDict("Observation", {"step": int, "cameras": dict[str, np.ndarray], "joint_positions": list[float], "joint_velocities": list[float]})`
  - `Action = TypedDict("Action", {"joint_positions": list[float]})`
  - `RobotBridge` protocol with `start()`, `observation_stream()`, `send_action(action)`, `sim_control(action, speed)`, `close()`, `bridge_status` property
  - `MockBridge` class implementing `RobotBridge`
  - `create_bridge(config: PlaygroundConfig) -> RobotBridge`

- [ ] **Step 1: Write bridge protocol and type tests**

Create `backend/tests/test_bridges.py`:

```python
from __future__ import annotations

import asyncio

import numpy as np
import pytest

from robotics_playground.bridges.protocol import Action, Observation


def test_observation_type_shape():
    obs: Observation = {
        "step": 0,
        "cameras": {"wrist": np.zeros((240, 320, 3), dtype=np.uint8)},
        "joint_positions": [0.0] * 6,
        "joint_velocities": [0.0] * 6,
    }
    assert obs["step"] == 0
    assert "wrist" in obs["cameras"]
    assert obs["cameras"]["wrist"].shape == (240, 320, 3)


def test_action_type_shape():
    act: Action = {"joint_positions": [0.0] * 7}
    assert len(act["joint_positions"]) == 7


@pytest.mark.anyio
async def test_mock_bridge_produces_observations():
    from robotics_playground.bridges.mock_bridge import MockBridge

    bridge = MockBridge()
    await bridge.start()

    count = 0
    async for obs in bridge.observation_stream():
        assert "cameras" in obs
        assert "wrist" in obs["cameras"]
        assert obs["cameras"]["wrist"].shape == (240, 320, 3)
        assert isinstance(obs["joint_positions"], list)
        assert isinstance(obs["joint_velocities"], list)
        assert obs["step"] == count
        count += 1
        if count >= 3:
            break

    await bridge.close()


@pytest.mark.anyio
async def test_mock_bridge_send_action_is_noop():
    from robotics_playground.bridges.mock_bridge import MockBridge

    bridge = MockBridge()
    await bridge.start()
    await bridge.send_action({"joint_positions": [0.0] * 7})
    await bridge.close()


@pytest.mark.anyio
async def test_mock_bridge_sim_control_is_noop():
    from robotics_playground.bridges.mock_bridge import MockBridge

    bridge = MockBridge()
    await bridge.start()
    await bridge.sim_control("play")
    await bridge.sim_control("pause")
    await bridge.sim_control("step")
    await bridge.sim_control("play", speed=2.0)
    await bridge.close()


@pytest.mark.anyio
async def test_mock_bridge_status_is_mock():
    from robotics_playground.bridges.mock_bridge import MockBridge

    bridge = MockBridge()
    assert bridge.bridge_status == "mock"
    await bridge.start()
    assert bridge.bridge_status == "mock"
    await bridge.close()


@pytest.mark.anyio
async def test_create_bridge_returns_mock_by_default():
    from robotics_playground.bridges import create_bridge
    from robotics_playground.bridges.mock_bridge import MockBridge
    from robotics_playground.config import PlaygroundConfig

    config = PlaygroundConfig()
    bridge = create_bridge(config)
    assert isinstance(bridge, MockBridge)
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `cd backend && uv run pytest tests/test_bridges.py -v`
Expected: FAIL — module `robotics_playground.bridges` doesn't exist yet

- [ ] **Step 3: Implement protocol types**

Create `backend/src/robotics_playground/bridges/protocol.py`:

```python
from __future__ import annotations

from collections.abc import AsyncIterator
from typing import Protocol, TypedDict

import numpy as np


class Observation(TypedDict):
    step: int
    cameras: dict[str, np.ndarray]
    joint_positions: list[float]
    joint_velocities: list[float]


class Action(TypedDict):
    joint_positions: list[float]


class RobotBridge(Protocol):
    @property
    def bridge_status(self) -> str: ...

    async def start(self) -> None: ...

    def observation_stream(self) -> AsyncIterator[Observation]: ...

    async def send_action(self, action: Action) -> None: ...

    async def sim_control(self, action: str, speed: float | None = None) -> None: ...

    async def close(self) -> None: ...
```

- [ ] **Step 4: Implement MockBridge**

Create `backend/src/robotics_playground/bridges/mock_bridge.py`:

```python
from __future__ import annotations

import asyncio
import math
import time
from collections.abc import AsyncIterator

import numpy as np

from robotics_playground.bridges.protocol import Action, Observation


class MockBridge:
    @property
    def bridge_status(self) -> str:
        return "mock"

    async def start(self) -> None:
        pass

    async def observation_stream(self) -> AsyncIterator[Observation]:
        step = 0
        while True:
            t = time.monotonic()
            image = np.zeros((240, 320, 3), dtype=np.uint8)
            image[:, :, 0] = np.arange(320) * 255 // 320
            image[:, :, 1] = int(127 + 127 * math.sin(t))

            positions = [math.sin(t + i * math.pi / 3) for i in range(6)]
            velocities = [math.cos(t + i * math.pi / 3) for i in range(6)]

            yield Observation(
                step=step,
                cameras={"wrist": image},
                joint_positions=positions,
                joint_velocities=velocities,
            )
            step += 1
            await asyncio.sleep(0.1)

    async def send_action(self, action: Action) -> None:
        pass

    async def sim_control(self, action: str, speed: float | None = None) -> None:
        pass

    async def close(self) -> None:
        pass
```

- [ ] **Step 5: Implement package init with factory**

Create `backend/src/robotics_playground/bridges/__init__.py`:

```python
from robotics_playground.bridges.mock_bridge import MockBridge
from robotics_playground.bridges.protocol import Action, Observation, RobotBridge
from robotics_playground.config import PlaygroundConfig

__all__ = ["Action", "MockBridge", "Observation", "RobotBridge", "create_bridge"]


def create_bridge(config: PlaygroundConfig) -> RobotBridge:
    if config.bridge.type == "ros2":
        from robotics_playground.bridges.ros2_bridge import ROS2Bridge

        return ROS2Bridge(config.ros2)
    return MockBridge()
```

- [ ] **Step 6: Run tests to verify they pass**

Run: `cd backend && uv run pytest tests/test_bridges.py -v`
Expected: All 6 tests PASS

- [ ] **Step 7: Lint and commit**

Run: `cd backend && uv run ruff check src/ tests/ && uv run ruff format --check src/ tests/`

```bash
git add backend/src/robotics_playground/bridges/ backend/tests/test_bridges.py
git commit -m "feat: add RobotBridge protocol and MockBridge implementation"
```

---

### Task 3: Refactor Session, RerunLogger, and Main to Use Bridge

**Files:**

- Modify: `backend/src/robotics_playground/session.py`
- Modify: `backend/src/robotics_playground/rerun_logger.py`
- Modify: `backend/src/robotics_playground/main.py`
- Modify: `backend/tests/test_session.py`
- Modify: `backend/tests/test_rerun_logger.py`
- Modify: `backend/tests/test_websocket.py`

**Interfaces:**

- Consumes: `RobotBridge` protocol, `Observation`, `Action`, `MockBridge`, `create_bridge(config)`, `load_config(path)`, `PlaygroundConfig`
- Produces: Updated `Session(bridge, rerun_logger)`, updated `RerunLogger.log_observation(obs, step)`, `bridge_status` in WebSocket status messages, `speed` param in sim_control handling

- [ ] **Step 1: Update RerunLogger tests**

Replace `backend/tests/test_rerun_logger.py` with tests for the new `log_observation(obs, step)` signature:

```python
from __future__ import annotations

from unittest.mock import MagicMock, patch

import numpy as np
import pytest


@pytest.fixture
def mock_rr():
    with patch("robotics_playground.rerun_logger.rr") as mock:
        yield mock


def test_log_observation_logs_all_cameras(mock_rr):
    from robotics_playground.rerun_logger import RerunLogger

    logger = RerunLogger()
    obs = {
        "step": 5,
        "cameras": {
            "wrist": np.zeros((240, 320, 3), dtype=np.uint8),
            "head": np.zeros((240, 320, 3), dtype=np.uint8),
        },
        "joint_positions": [0.1, 0.2, 0.3],
        "joint_velocities": [0.0, 0.0, 0.0],
    }
    logger.log_observation(obs, step=5)

    mock_rr.set_time.assert_called_with("step", sequence=5)

    logged_paths = [call.args[0] for call in mock_rr.log.call_args_list]
    assert "session/policy_0/camera/wrist" in logged_paths
    assert "session/policy_0/camera/head" in logged_paths


def test_log_observation_logs_joint_positions(mock_rr):
    from robotics_playground.rerun_logger import RerunLogger

    logger = RerunLogger()
    obs = {
        "step": 0,
        "cameras": {"wrist": np.zeros((240, 320, 3), dtype=np.uint8)},
        "joint_positions": [0.1, 0.2, 0.3],
        "joint_velocities": [0.4, 0.5, 0.6],
    }
    logger.log_observation(obs, step=0)

    logged_paths = [call.args[0] for call in mock_rr.log.call_args_list]
    assert "session/policy_0/joints/joint_0" in logged_paths
    assert "session/policy_0/joints/joint_2" in logged_paths


def test_log_action_logs_dimensions(mock_rr):
    from robotics_playground.rerun_logger import RerunLogger

    logger = RerunLogger()
    action = {"joint_positions": [0.1, 0.2, 0.3]}
    logger.log_action(action, step=1)

    mock_rr.set_time.assert_called_with("step", sequence=1)
    logged_paths = [call.args[0] for call in mock_rr.log.call_args_list]
    assert "session/policy_0/actions/dim_0" in logged_paths


def test_log_instruction(mock_rr):
    from robotics_playground.rerun_logger import RerunLogger

    logger = RerunLogger()
    logger.log_instruction("pick up block", step=3)
    mock_rr.set_time.assert_called_with("step", sequence=3)
    mock_rr.log.assert_called()
```

- [ ] **Step 2: Update RerunLogger implementation**

Replace `backend/src/robotics_playground/rerun_logger.py`:

```python
from __future__ import annotations

from typing import TYPE_CHECKING

import rerun as rr

if TYPE_CHECKING:
    from robotics_playground.bridges.protocol import Action, Observation


class RerunLogger:
    def __init__(self, port: int = 9876, web_port: int = 9090, policy_index: int = 0):
        self._port = port
        self._web_port = web_port
        self._prefix = f"session/policy_{policy_index}"
        self._initialized = False

    def start(self):
        if self._initialized:
            return
        rr.init("robotics_playground")
        server_uri = rr.serve_grpc(grpc_port=self._port)
        rr.serve_web_viewer(
            web_port=self._web_port,
            open_browser=False,
            connect_to=server_uri,
        )
        self._initialized = True

    def log_observation(self, obs: Observation, step: int):
        rr.set_time("step", sequence=step)
        for name, image in obs["cameras"].items():
            rr.log(f"{self._prefix}/camera/{name}", rr.Image(image))
        for i, pos in enumerate(obs["joint_positions"]):
            rr.log(f"{self._prefix}/joints/joint_{i}", rr.Scalars(pos))

    def log_action(self, action: Action, step: int):
        rr.set_time("step", sequence=step)
        for i, val in enumerate(action["joint_positions"]):
            rr.log(f"{self._prefix}/actions/dim_{i}", rr.Scalars(float(val)))

    def log_instruction(self, text: str, step: int):
        rr.set_time("step", sequence=step)
        rr.log("session/instructions", rr.TextLog(text))
```

- [ ] **Step 3: Run RerunLogger tests**

Run: `cd backend && uv run pytest tests/test_rerun_logger.py -v`
Expected: All PASS

- [ ] **Step 4: Update Session tests**

Replace `backend/tests/test_session.py` with tests that use `MockBridge`:

```python
from __future__ import annotations

import asyncio
from unittest.mock import MagicMock

import pytest

from robotics_playground.bridges.mock_bridge import MockBridge
from robotics_playground.session import Session


def _make_mock_logger():
    logger = MagicMock()
    logger.log_observation = MagicMock()
    logger.log_action = MagicMock()
    logger.log_instruction = MagicMock()
    return logger


def test_session_initial_state():
    session = Session(bridge=MockBridge(), rerun_logger=_make_mock_logger())
    assert session.state == "idle"
    assert session.step == 0
    assert session.instruction == ""


def test_send_instruction_stores_text():
    session = Session(bridge=MockBridge(), rerun_logger=_make_mock_logger())
    session.send_instruction("wave")
    assert session.instruction == "wave"


@pytest.mark.anyio
async def test_start_stop_lifecycle():
    session = Session(bridge=MockBridge(), rerun_logger=_make_mock_logger())
    await session.start()
    assert session.state == "running"
    await session.stop()
    assert session.state == "idle"


@pytest.mark.anyio
async def test_start_is_idempotent():
    session = Session(bridge=MockBridge(), rerun_logger=_make_mock_logger())
    await session.start()
    await session.start()
    assert session.state == "running"
    await session.stop()


@pytest.mark.anyio
async def test_stop_from_idle_is_noop():
    session = Session(bridge=MockBridge(), rerun_logger=_make_mock_logger())
    await session.stop()
    assert session.state == "idle"


@pytest.mark.anyio
async def test_pause_resume():
    session = Session(bridge=MockBridge(), rerun_logger=_make_mock_logger())
    await session.start()
    session.pause()
    assert session.state == "paused"
    session.resume()
    assert session.state == "running"
    await session.stop()


@pytest.mark.anyio
async def test_reset_clears_state():
    session = Session(bridge=MockBridge(), rerun_logger=_make_mock_logger())
    await session.start()
    session.send_instruction("pick up block")
    await session.reset()
    assert session.state == "idle"
    assert session.instruction == ""


@pytest.mark.anyio
async def test_handle_sim_control_play_from_idle():
    session = Session(bridge=MockBridge(), rerun_logger=_make_mock_logger())
    await session.handle_sim_control("play")
    assert session.state == "running"
    await session.stop()


@pytest.mark.anyio
async def test_handle_sim_control_with_speed():
    session = Session(bridge=MockBridge(), rerun_logger=_make_mock_logger())
    await session.handle_sim_control("play", speed=2.0)
    assert session.state == "running"
    await session.stop()


@pytest.mark.anyio
async def test_handle_sim_control_step():
    session = Session(bridge=MockBridge(), rerun_logger=_make_mock_logger())
    await session.handle_sim_control("step")
    assert session.state == "paused"
    await session.stop()


@pytest.mark.anyio
async def test_bridge_status_exposed():
    bridge = MockBridge()
    session = Session(bridge=bridge, rerun_logger=_make_mock_logger())
    assert session.bridge_status == "mock"


@pytest.mark.anyio
async def test_observation_loop_logs_data():
    mock_logger = _make_mock_logger()
    session = Session(bridge=MockBridge(), rerun_logger=mock_logger)
    await session.start()
    await asyncio.sleep(0.35)
    await session.stop()
    assert mock_logger.log_observation.call_count >= 2
    assert mock_logger.log_action.call_count >= 2
```

- [ ] **Step 5: Implement updated Session**

Replace `backend/src/robotics_playground/session.py`:

```python
from __future__ import annotations

import asyncio
import contextlib
from typing import TYPE_CHECKING

from robotics_playground.mock_policy import predict_action

if TYPE_CHECKING:
    from robotics_playground.bridges.protocol import RobotBridge
    from robotics_playground.rerun_logger import RerunLogger


class Session:
    def __init__(self, bridge: RobotBridge, rerun_logger: RerunLogger):
        self._bridge = bridge
        self._logger = rerun_logger
        self._task: asyncio.Task | None = None
        self._instruction: str = ""
        self._state: str = "idle"
        self._step: int = 0
        self._paused = asyncio.Event()
        self._paused.set()
        self._step_once = asyncio.Event()

    @property
    def state(self) -> str:
        return self._state

    @property
    def step(self) -> int:
        return self._step

    @property
    def instruction(self) -> str:
        return self._instruction

    @property
    def bridge_status(self) -> str:
        return self._bridge.bridge_status

    def send_instruction(self, text: str):
        self._instruction = text

    async def start(self):
        if self._task is not None:
            return
        self._state = "running"
        self._paused.set()
        await self._bridge.start()
        self._task = asyncio.create_task(self._run_loop())

    async def stop(self):
        if self._task is None:
            return
        self._task.cancel()
        self._paused.set()
        self._step_once.clear()
        with contextlib.suppress(asyncio.CancelledError):
            await self._task
        self._task = None
        await self._bridge.close()
        self._state = "idle"
        self._step = 0

    def pause(self):
        if self._state == "running":
            self._paused.clear()
            self._state = "paused"

    def resume(self):
        if self._state == "paused":
            self._paused.set()
            self._state = "running"

    def step_once(self):
        if self._state == "paused":
            self._step_once.set()

    async def reset(self):
        await self.stop()
        self._instruction = ""

    async def handle_sim_control(self, action: str, speed: float | None = None):
        if action == "play":
            if self._state == "idle":
                await self.start()
            else:
                self.resume()
            await self._bridge.sim_control("play", speed=speed)
        elif action == "pause":
            self.pause()
            await self._bridge.sim_control("pause")
        elif action == "stop":
            await self._bridge.sim_control("stop")
            await self.stop()
        elif action == "step":
            if self._state == "idle":
                await self.start()
                self.pause()
            await self._bridge.sim_control("step")
            self.step_once()
        elif action == "reset":
            await self._bridge.sim_control("reset")
            await self.reset()

    async def _run_loop(self):
        try:
            async for obs in self._bridge.observation_stream():
                paused_future = asyncio.ensure_future(self._paused.wait())
                step_future = asyncio.ensure_future(self._step_once.wait())
                try:
                    _, pending = await asyncio.wait(
                        [paused_future, step_future],
                        return_when=asyncio.FIRST_COMPLETED,
                    )
                    for f in pending:
                        f.cancel()
                finally:
                    paused_future.cancel()
                    step_future.cancel()

                stepping = self._step_once.is_set()
                if stepping:
                    self._step_once.clear()

                self._step = obs["step"]
                self._logger.log_observation(obs, obs["step"])

                if self._instruction:
                    self._logger.log_instruction(self._instruction, obs["step"])

                action = await predict_action(obs)
                self._logger.log_action(action, obs["step"])

                await self._bridge.send_action(action)

                if stepping:
                    self._paused.clear()
        except asyncio.CancelledError:
            raise
```

- [ ] **Step 6: Run Session tests**

Run: `cd backend && uv run pytest tests/test_session.py -v`
Expected: All PASS

- [ ] **Step 7: Update mock_policy to return Action dict**

Replace `backend/src/robotics_playground/mock_policy.py`:

```python
from __future__ import annotations

import asyncio

import numpy as np

from robotics_playground.bridges.protocol import Action


async def predict_action(observation: dict) -> Action:
    await asyncio.sleep(0.05)
    positions = np.random.uniform(-1.0, 1.0, size=(6,)).tolist()
    return Action(joint_positions=positions)
```

- [ ] **Step 8: Update mock_policy tests**

Replace `backend/tests/test_mock_policy.py`:

```python
from __future__ import annotations

import pytest

from robotics_playground.mock_policy import predict_action


@pytest.mark.anyio
async def test_predict_action_returns_action_dict():
    obs = {"step": 0, "cameras": {}, "joint_positions": [0.0] * 6, "joint_velocities": [0.0] * 6}
    action = await predict_action(obs)
    assert "joint_positions" in action
    assert len(action["joint_positions"]) == 6
    assert all(isinstance(v, float) for v in action["joint_positions"])
```

- [ ] **Step 9: Update WebSocket tests for bridge_status and speed**

Add these tests to `backend/tests/test_websocket.py` (append, don't replace — existing tests should still work after the main.py update):

The existing tests in `test_websocket.py` will need the test client fixture updated. Replace the full file:

```python
from __future__ import annotations

import pytest
from httpx import ASGITransport, AsyncClient

from robotics_playground.bridges.mock_bridge import MockBridge
from robotics_playground.main import app


@pytest.fixture
def anyio_backend():
    return "asyncio"


@pytest.mark.anyio
async def test_websocket_status_includes_bridge_status():
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as _:
        async with app.router.lifespan_context(app):
            from starlette.testclient import TestClient

            client = TestClient(app)
            with client.websocket_connect("/ws/sessions/test-session") as ws:
                data = ws.receive_json()
                assert data["type"] == "status"
                assert "bridge_status" in data
                assert data["bridge_status"] == "mock"


@pytest.mark.anyio
async def test_websocket_instruction_flow():
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as _:
        async with app.router.lifespan_context(app):
            from starlette.testclient import TestClient

            client = TestClient(app)
            with client.websocket_connect("/ws/sessions/test-session") as ws:
                _ = ws.receive_json()  # initial status
                ws.send_json({"type": "instruction", "text": "wave"})
                ack = ws.receive_json()
                assert ack["type"] == "instruction_ack"
                assert ack["status"] == "received"
                assert ack["text"] == "wave"


@pytest.mark.anyio
async def test_websocket_sim_control_with_speed():
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as _:
        async with app.router.lifespan_context(app):
            from starlette.testclient import TestClient

            client = TestClient(app)
            with client.websocket_connect("/ws/sessions/test-session") as ws:
                _ = ws.receive_json()
                ws.send_json({"type": "sim_control", "action": "play", "speed": 2.0})
                status = ws.receive_json()
                assert status["type"] == "status"
```

- [ ] **Step 10: Update main.py to use config and bridge**

Replace `backend/src/robotics_playground/main.py`:

```python
from __future__ import annotations

import asyncio
import contextlib
import json
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
    logger = RerunLogger(port=config.rerun.grpc_port, web_port=config.rerun.web_port)
    logger.start()
    bridge = create_bridge(config)
    session = Session(bridge=bridge, rerun_logger=logger)
    app.state.rerun_logger = logger
    app.state.session = session
    yield
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
        await session.stop()
```

- [ ] **Step 11: Run all backend tests**

Run: `cd backend && uv run pytest -v`
Expected: All tests PASS

- [ ] **Step 12: Lint and commit**

Run: `cd backend && uv run ruff check src/ tests/ && uv run ruff format --check src/ tests/`

```bash
git add backend/src/robotics_playground/ backend/tests/
git commit -m "refactor: wire Session and RerunLogger to RobotBridge abstraction"
```

---

### Task 4: ROS2Bridge Implementation

**Files:**

- Create: `backend/src/robotics_playground/bridges/ros2_bridge.py`
- Create: `backend/tests/test_ros2_bridge.py`

**Interfaces:**

- Consumes: `RobotBridge` protocol, `Observation`, `Action`, `ROS2Config` from config
- Produces: `ROS2Bridge(config: ROS2Config)` class implementing `RobotBridge`

- [ ] **Step 1: Write ROS2Bridge tests with mocked rclpy**

Create `backend/tests/test_ros2_bridge.py`:

```python
from __future__ import annotations

import asyncio
from unittest.mock import MagicMock, patch

import numpy as np
import pytest


@pytest.fixture
def mock_rclpy():
    mock_node = MagicMock()
    mock_node.create_subscription = MagicMock()
    mock_node.create_publisher = MagicMock()
    mock_node.create_client = MagicMock()
    mock_node.destroy_node = MagicMock()

    mock_rclpy_module = MagicMock()
    mock_rclpy_module.init = MagicMock()
    mock_rclpy_module.shutdown = MagicMock()

    mock_node_class = MagicMock(return_value=mock_node)

    mocks = {
        "rclpy": mock_rclpy_module,
        "rclpy.node": MagicMock(Node=mock_node_class),
        "rclpy.executors": MagicMock(),
        "rclpy.qos": MagicMock(),
        "sensor_msgs": MagicMock(),
        "sensor_msgs.msg": MagicMock(),
        "trajectory_msgs": MagicMock(),
        "trajectory_msgs.msg": MagicMock(),
        "simulation_interfaces": MagicMock(),
        "simulation_interfaces.srv": MagicMock(),
    }

    with patch.dict("sys.modules", mocks):
        yield {
            "rclpy": mock_rclpy_module,
            "node": mock_node,
            "node_class": mock_node_class,
        }


def test_ros2_bridge_creates_node(mock_rclpy):
    from robotics_playground.bridges.ros2_bridge import ROS2Bridge
    from robotics_playground.config import ROS2Config

    config = ROS2Config(cameras={"wrist": "/cam/wrist"})
    bridge = ROS2Bridge(config)

    assert bridge.bridge_status == "disconnected"


def test_ros2_bridge_initial_status_is_disconnected(mock_rclpy):
    from robotics_playground.bridges.ros2_bridge import ROS2Bridge
    from robotics_playground.config import ROS2Config

    bridge = ROS2Bridge(ROS2Config(cameras={"wrist": "/cam/wrist"}))
    assert bridge.bridge_status == "disconnected"


@pytest.mark.anyio
async def test_ros2_bridge_start_initializes_rclpy(mock_rclpy):
    from robotics_playground.bridges.ros2_bridge import ROS2Bridge
    from robotics_playground.config import ROS2Config

    bridge = ROS2Bridge(ROS2Config(cameras={"wrist": "/cam/wrist"}))
    await bridge.start()
    mock_rclpy["rclpy"].init.assert_called_once()
    assert bridge.bridge_status == "connected"
    await bridge.close()


@pytest.mark.anyio
async def test_ros2_bridge_close_shuts_down(mock_rclpy):
    from robotics_playground.bridges.ros2_bridge import ROS2Bridge
    from robotics_playground.config import ROS2Config

    bridge = ROS2Bridge(ROS2Config(cameras={"wrist": "/cam/wrist"}))
    await bridge.start()
    await bridge.close()
    mock_rclpy["rclpy"].shutdown.assert_called_once()
    assert bridge.bridge_status == "disconnected"


@pytest.mark.anyio
async def test_ros2_bridge_observation_from_callbacks(mock_rclpy):
    from robotics_playground.bridges.ros2_bridge import ROS2Bridge
    from robotics_playground.config import ROS2Config

    config = ROS2Config(cameras={"wrist": "/cam/wrist"})
    bridge = ROS2Bridge(config)
    await bridge.start()

    image_data = np.zeros((240, 320, 3), dtype=np.uint8)
    bridge._on_image_received("wrist", image_data)
    bridge._on_joint_state_received([0.1, 0.2, 0.3], [0.0, 0.0, 0.0])

    obs = None
    async for o in bridge.observation_stream():
        obs = o
        break

    assert obs is not None
    assert "wrist" in obs["cameras"]
    assert obs["joint_positions"] == [0.1, 0.2, 0.3]
    await bridge.close()
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `cd backend && uv run pytest tests/test_ros2_bridge.py -v`
Expected: FAIL — `ros2_bridge` module doesn't exist

- [ ] **Step 3: Implement ROS2Bridge**

Create `backend/src/robotics_playground/bridges/ros2_bridge.py`:

```python
from __future__ import annotations

import asyncio
import threading
from collections.abc import AsyncIterator
from typing import TYPE_CHECKING

import numpy as np

from robotics_playground.bridges.protocol import Action, Observation

if TYPE_CHECKING:
    from robotics_playground.config import ROS2Config


class ROS2Bridge:
    def __init__(self, config: ROS2Config):
        self._config = config
        self._node = None
        self._executor = None
        self._spin_thread: threading.Thread | None = None
        self._obs_queue: asyncio.Queue[Observation] = asyncio.Queue(maxsize=10)
        self._step = 0
        self._latest_cameras: dict[str, np.ndarray] = {}
        self._latest_joint_positions: list[float] = []
        self._latest_joint_velocities: list[float] = []
        self._loop: asyncio.AbstractEventLoop | None = None
        self._status = "disconnected"
        self._publisher = None
        self._sim_state_client = None
        self._step_client = None

    @property
    def bridge_status(self) -> str:
        return self._status

    async def start(self) -> None:
        import rclpy
        from rclpy.executors import SingleThreadedExecutor
        from rclpy.node import Node

        self._loop = asyncio.get_running_loop()

        rclpy.init(domain_id=self._config.domain_id)
        self._node = Node("robotics_playground_bridge")
        self._executor = SingleThreadedExecutor()
        self._executor.add_node(self._node)

        from sensor_msgs.msg import Image, JointState

        for name, topic in self._config.cameras.items():
            self._node.create_subscription(
                Image,
                topic,
                lambda msg, n=name: self._handle_image(n, msg),
                10,
            )

        self._node.create_subscription(
            JointState,
            self._config.joint_state_topic,
            self._handle_joint_state,
            10,
        )

        from trajectory_msgs.msg import JointTrajectory

        self._publisher = self._node.create_publisher(
            JointTrajectory,
            self._config.joint_command_topic,
            10,
        )

        from simulation_interfaces.srv import SetSimulationState, StepSimulation

        self._sim_state_client = self._node.create_client(
            SetSimulationState, "/set_simulation_state"
        )
        self._step_client = self._node.create_client(
            StepSimulation, "/step_simulation"
        )

        self._spin_thread = threading.Thread(target=self._spin, daemon=True)
        self._spin_thread.start()
        self._status = "connected"

    def _spin(self):
        while self._executor is not None:
            self._executor.spin_once(timeout_sec=0.1)

    def _handle_image(self, camera_name: str, msg):
        data = np.frombuffer(msg.data, dtype=np.uint8).reshape(msg.height, msg.width, -1)
        self._on_image_received(camera_name, data)

    def _handle_joint_state(self, msg):
        self._on_joint_state_received(list(msg.position), list(msg.velocity))

    def _on_image_received(self, camera_name: str, image: np.ndarray):
        self._latest_cameras[camera_name] = image
        if self._latest_joint_positions and self._loop is not None:
            obs = Observation(
                step=self._step,
                cameras=dict(self._latest_cameras),
                joint_positions=list(self._latest_joint_positions),
                joint_velocities=list(self._latest_joint_velocities),
            )
            self._step += 1
            try:
                self._loop.call_soon_threadsafe(self._obs_queue.put_nowait, obs)
            except asyncio.QueueFull:
                pass

    def _on_joint_state_received(self, positions: list[float], velocities: list[float]):
        self._latest_joint_positions = positions
        self._latest_joint_velocities = velocities

    async def observation_stream(self) -> AsyncIterator[Observation]:
        while True:
            obs = await self._obs_queue.get()
            yield obs

    async def send_action(self, action: Action) -> None:
        if self._publisher is None or self._node is None:
            return
        from trajectory_msgs.msg import JointTrajectory, JointTrajectoryPoint

        msg = JointTrajectory()
        point = JointTrajectoryPoint()
        point.positions = [float(p) for p in action["joint_positions"]]
        msg.points = [point]
        self._publisher.publish(msg)

    async def sim_control(self, action: str, speed: float | None = None) -> None:
        if self._node is None:
            return

        if action in ("play", "pause", "stop"):
            from simulation_interfaces.srv import SetSimulationState

            state_map = {"stop": 0, "play": 1, "pause": 2}
            req = SetSimulationState.Request()
            req.state.data = state_map[action]
            if self._sim_state_client is not None:
                await asyncio.get_running_loop().run_in_executor(
                    None, lambda: self._sim_state_client.call(req)
                )

        elif action == "step":
            from simulation_interfaces.srv import StepSimulation

            req = StepSimulation.Request()
            req.num_steps = 1
            if self._step_client is not None:
                await asyncio.get_running_loop().run_in_executor(
                    None, lambda: self._step_client.call(req)
                )

        elif action == "reset":
            from simulation_interfaces.srv import SetSimulationState

            req = SetSimulationState.Request()
            req.state.data = 0  # STATE_STOPPED
            if self._sim_state_client is not None:
                await asyncio.get_running_loop().run_in_executor(
                    None, lambda: self._sim_state_client.call(req)
                )

    async def close(self) -> None:
        if self._executor is not None:
            self._executor.shutdown()
            self._executor = None
        if self._spin_thread is not None:
            self._spin_thread.join(timeout=2.0)
            self._spin_thread = None
        if self._node is not None:
            self._node.destroy_node()
            self._node = None
        import rclpy

        rclpy.shutdown()
        self._status = "disconnected"
```

- [ ] **Step 4: Run ROS2Bridge tests**

Run: `cd backend && uv run pytest tests/test_ros2_bridge.py -v`
Expected: All 5 tests PASS

- [ ] **Step 5: Run all backend tests**

Run: `cd backend && uv run pytest -v`
Expected: All tests PASS

- [ ] **Step 6: Lint and commit**

Run: `cd backend && uv run ruff check src/ tests/ && uv run ruff format --check src/ tests/`

```bash
git add backend/src/robotics_playground/bridges/ros2_bridge.py backend/tests/test_ros2_bridge.py
git commit -m "feat: add ROS2Bridge with rclpy node for Isaac Sim communication"
```

---

### Task 5: Frontend — Speed Slider and Bridge Status

**Files:**

- Modify: `frontend/src/hooks/useSession.ts`
- Modify: `frontend/src/components/SimulationControlPanel.tsx`
- Modify: `frontend/src/RoboticsPlayground.tsx`
- Modify: `frontend/test/SimulationControlPanel.test.tsx`
- Modify: `frontend/test/useSession.test.ts`

**Interfaces:**

- Consumes: WebSocket `status` messages now include `bridge_status` field; `sim_control` messages now accept `speed` field
- Produces: Updated `SimulationControlPanel` with speed slider and bridge status label; updated `useSession` hook with `bridgeStatus` and speed-aware `sendSimControl`

- [ ] **Step 1: Update useSession hook tests**

Add to `frontend/test/useSession.test.ts` — find the test for status message handling and verify it now expects `bridgeStatus`. If the test file uses a WebSocket mock, update the mock status message to include `bridge_status: "mock"`.

Add this test case (append to the existing describe block):

```typescript
it('parses bridge_status from status messages', async () => {
  // In the existing mock WebSocket setup, send:
  // { type: 'status', state: 'idle', step: 0, instruction: '', bridge_status: 'mock' }
  // Verify that sessionState.bridgeStatus === 'mock'
});
```

The exact integration depends on the existing test structure. The key change: `SessionState` gains `bridgeStatus: string` and `sendSimControl` gains an optional `speed` parameter.

- [ ] **Step 2: Update useSession hook**

Modify `frontend/src/hooks/useSession.ts`:

Add `bridgeStatus` to `SessionState`:

```typescript
export interface SessionState {
  state: string;
  step: number;
  instruction: string;
  bridgeStatus: string;
}
```

Update the default state:

```typescript
const [sessionState, setSessionState] = useState<SessionState>({
  state: 'idle',
  step: 0,
  instruction: '',
  bridgeStatus: 'mock',
});
```

Update the status message handler to include `bridgeStatus`:

```typescript
if (msg.type === 'status') {
  setSessionState({
    state: msg.state ?? 'idle',
    step: msg.step ?? 0,
    instruction: msg.instruction ?? '',
    bridgeStatus: msg.bridge_status ?? 'mock',
  });
}
```

Update `sendSimControl` to accept an optional speed:

```typescript
const sendSimControl = useCallback((action: string, speed?: number) => {
  if (wsRef.current?.readyState === WebSocket.OPEN) {
    const msg: Record<string, unknown> = { type: 'sim_control', action };
    if (speed !== undefined) {
      msg.speed = speed;
    }
    wsRef.current.send(JSON.stringify(msg));
  }
}, []);
```

Update the `UseSessionReturn` interface:

```typescript
export interface UseSessionReturn {
  connected: boolean;
  sessionState: SessionState;
  messages: ChatMessage[];
  sendInstruction: (text: string) => void;
  sendSimControl: (action: string, speed?: number) => void;
}
```

- [ ] **Step 3: Update SimulationControlPanel tests**

Add tests to `frontend/test/SimulationControlPanel.test.tsx`:

```typescript
it('renders bridge status label', () => {
  render(
    <SimulationControlPanel
      state="idle"
      bridgeStatus="mock"
      onSimControl={vi.fn()}
    />
  );
  expect(screen.getByText('Mock')).toBeInTheDocument();
});

it('shows Connected label for connected bridge', () => {
  render(
    <SimulationControlPanel
      state="running"
      bridgeStatus="connected"
      onSimControl={vi.fn()}
    />
  );
  expect(screen.getByText('Connected')).toBeInTheDocument();
});

it('shows Disconnected label for disconnected bridge', () => {
  render(
    <SimulationControlPanel
      state="idle"
      bridgeStatus="disconnected"
      onSimControl={vi.fn()}
    />
  );
  expect(screen.getByText('Disconnected')).toBeInTheDocument();
});

it('renders speed slider', () => {
  render(
    <SimulationControlPanel
      state="running"
      bridgeStatus="mock"
      onSimControl={vi.fn()}
    />
  );
  expect(screen.getByRole('slider')).toBeInTheDocument();
});
```

Update all existing tests to pass `bridgeStatus="mock"`:

```typescript
// Every existing render call needs updating, e.g.:
render(<SimulationControlPanel state="idle" bridgeStatus="mock" onSimControl={vi.fn()} />);
```

- [ ] **Step 4: Update SimulationControlPanel component**

Replace `frontend/src/components/SimulationControlPanel.tsx`:

```tsx
import React, { useState } from 'react';
import {
  Button,
  Content,
  Flex,
  FlexItem,
  Label,
  Slider,
} from '@patternfly/react-core';

interface SimulationControlPanelProps {
  state: string;
  bridgeStatus: string;
  onSimControl: (action: string, speed?: number) => void;
}

const STATE_LABELS: Record<string, { text: string; color: 'grey' | 'green' | 'orange' | 'red' }> = {
  idle: { text: 'Idle', color: 'grey' },
  running: { text: 'Running', color: 'green' },
  paused: { text: 'Paused', color: 'orange' },
  error: { text: 'Error', color: 'red' },
};

const BRIDGE_LABELS: Record<string, { text: string; color: 'grey' | 'green' | 'red' }> = {
  mock: { text: 'Mock', color: 'grey' },
  connected: { text: 'Connected', color: 'green' },
  disconnected: { text: 'Disconnected', color: 'red' },
};

const SimulationControlPanel: React.FC<SimulationControlPanelProps> = ({
  state,
  bridgeStatus,
  onSimControl,
}) => {
  const [speed, setSpeed] = useState(1.0);
  const label = STATE_LABELS[state] ?? STATE_LABELS.idle;
  const bridgeLabel = BRIDGE_LABELS[bridgeStatus] ?? BRIDGE_LABELS.mock;
  const isRunning = state === 'running';
  const isPaused = state === 'paused';

  return (
    <div className="simulation-control-panel">
      <Flex justifyContent={{ default: 'justifyContentSpaceBetween' }} alignItems={{ default: 'alignItemsCenter' }}>
        <FlexItem>
          <Content component="h2" style={{ margin: 0 }}>Simulation Control</Content>
        </FlexItem>
        <FlexItem>
          <Flex spaceItems={{ default: 'spaceItemsSm' }}>
            <FlexItem>
              <Label color={bridgeLabel.color}>{bridgeLabel.text}</Label>
            </FlexItem>
            <FlexItem>
              <Label color={label.color}>{label.text}</Label>
            </FlexItem>
          </Flex>
        </FlexItem>
      </Flex>
      <Flex alignItems={{ default: 'alignItemsCenter' }}>
        <FlexItem>
          <Button
            variant="primary"
            size="sm"
            onClick={() => onSimControl(isRunning ? 'pause' : 'play', speed)}
          >
            {isRunning ? 'Pause' : 'Play'}
          </Button>
        </FlexItem>
        <FlexItem>
          <Button
            variant="danger"
            size="sm"
            onClick={() => onSimControl('stop')}
            isDisabled={!isRunning && !isPaused}
          >
            Stop
          </Button>
        </FlexItem>
        <FlexItem>
          <Button
            variant="secondary"
            size="sm"
            onClick={() => onSimControl('step')}
            isDisabled={isRunning}
          >
            Step
          </Button>
        </FlexItem>
        <FlexItem>
          <Button
            variant="secondary"
            size="sm"
            onClick={() => onSimControl('reset')}
          >
            Reset
          </Button>
        </FlexItem>
      </Flex>
      <Flex alignItems={{ default: 'alignItemsCenter' }}>
        <FlexItem>
          <Content component="small">Speed: {speed.toFixed(1)}x</Content>
        </FlexItem>
        <FlexItem grow={{ default: 'grow' }}>
          <Slider
            value={speed * 10}
            min={1}
            max={50}
            onChange={(_event, val) => setSpeed(val / 10)}
            aria-label="Simulation speed"
          />
        </FlexItem>
      </Flex>
    </div>
  );
};

export default SimulationControlPanel;
```

- [ ] **Step 5: Update RoboticsPlayground to pass bridgeStatus**

In `frontend/src/RoboticsPlayground.tsx`, update the `SimulationControlPanel` usage:

```tsx
<SimulationControlPanel
  state={sessionState.state}
  bridgeStatus={sessionState.bridgeStatus}
  onSimControl={sendSimControl}
/>
```

- [ ] **Step 6: Run frontend tests**

Run: `cd frontend && npm test`
Expected: All tests PASS

- [ ] **Step 7: Run frontend linting**

Run: `cd frontend && npm run lint && npm run typecheck`
Expected: PASS

- [ ] **Step 8: Commit**

```bash
git add frontend/src/ frontend/test/
git commit -m "feat(frontend): add speed slider and bridge status indicator"
```

---

### Task 6: Backend Containerfile — UBI9 + ROS 2

**Files:**

- Modify: `backend/Containerfile`

**Interfaces:**

- Consumes: All backend source code, `pyproject.toml`
- Produces: Container image `robotics-playground:local` based on UBI9 with ROS 2 Jazzy

- [ ] **Step 1: Replace backend Containerfile**

Replace `backend/Containerfile`:

```dockerfile
FROM registry.access.redhat.com/ubi9/python-312 AS builder

USER 0
WORKDIR /build

RUN dnf install -y \
    https://dl.fedoraproject.org/pub/epel/epel-release-latest-9.noarch.rpm && \
    dnf install -y \
    gcc \
    python3-devel && \
    dnf clean all

COPY pyproject.toml ./
COPY src/ src/
RUN pip install --no-cache-dir --prefix=/install .

FROM registry.access.redhat.com/ubi9/python-312

USER 0

RUN dnf install -y \
    https://dl.fedoraproject.org/pub/epel/epel-release-latest-9.noarch.rpm && \
    curl -sSL https://raw.githubusercontent.com/ros/rosdistro/master/ros.key \
    -o /usr/share/keyrings/ros-archive-keyring.gpg && \
    dnf config-manager --add-repo \
    https://packages.ros.org/ros2/rhel/9/x86_64/ && \
    dnf install -y --nogpgcheck \
    ros-jazzy-rclpy \
    ros-jazzy-sensor-msgs \
    ros-jazzy-trajectory-msgs \
    ros-jazzy-simulation-interfaces && \
    dnf clean all

COPY --from=builder /install /usr/local
COPY src/ /app/src/

WORKDIR /app
EXPOSE 8000 9876 9090

ENV PLAYGROUND_CONFIG=/etc/robotics-playground/config.yaml

CMD ["uvicorn", "robotics_playground.main:app", "--host", "0.0.0.0", "--port", "8000"]
```

Note: The exact ROS 2 RPM installation steps may need adjustment based on RHEL 9 / ROS 2 Jazzy availability. The engineer should verify the RPM repo URL and package names. If official ROS 2 RPMs aren't available for UBI9, fall back to building from source or using the ROS 2 OSRF repos for RHEL 9.

- [ ] **Step 2: Build the container image**

Run: `make build-backend-image`
Expected: Image builds successfully. If ROS 2 RPM installation fails, adjust the repo URL and package names.

- [ ] **Step 3: Verify the container starts in mock mode**

Run:

```bash
podman run --rm -p 8000:8000 robotics-playground:local &
sleep 3
curl http://localhost:8000/api/health
podman stop $(podman ps -q --filter ancestor=robotics-playground:local)
```

Expected: `{"status":"ok"}`

- [ ] **Step 4: Commit**

```bash
git add backend/Containerfile
git commit -m "build: switch backend to UBI9 base with ROS 2 Jazzy"
```

---

### Task 7: Deployment Manifests — ConfigMap, Compose, Kustomize

**Files:**

- Modify: `deploy/compose.yaml`
- Create: `deploy/kustomize/configmap.yaml`
- Create: `deploy/kustomize/config/playground.yaml`
- Modify: `deploy/kustomize/kustomization.yaml`
- Modify: `deploy/kustomize/backend-deployment.yaml`
- Modify: `Makefile`

**Interfaces:**

- Consumes: Config files from Task 1, container images from Task 6
- Produces: Updated deployment stack with config mounting and optional Isaac Sim

- [ ] **Step 1: Update compose.yaml**

Replace `deploy/compose.yaml`:

```yaml
services:
  ui:
    image: robotics-playground-ui:${TAG:-local}
    ports:
      - "8080:8080"
    depends_on:
      backend:
        condition: service_started

  backend:
    image: robotics-playground:${TAG:-local}
    ports:
      - "8000:8000"
      - "9876:9876"
      - "9090:9090"
    volumes:
      - ./config/playground.yaml:/etc/robotics-playground/config.yaml:ro
    environment:
      PLAYGROUND_CONFIG: /etc/robotics-playground/config.yaml

  isaac-sim:
    image: nvcr.io/nvidia/isaac-sim:4.5.0
    profiles:
      - gpu
    deploy:
      resources:
        reservations:
          devices:
            - capabilities: [gpu]
```

- [ ] **Step 2: Create Kustomize ConfigMap**

Create `deploy/kustomize/config/playground.yaml`:

```yaml
server:
  host: "0.0.0.0"
  port: 8000
  log_level: "info"

rerun:
  grpc_port: 9876
  web_port: 9090

bridge:
  type: "mock"
```

Create `deploy/kustomize/configmap.yaml`:

```yaml
apiVersion: v1
kind: ConfigMap
metadata:
  name: robotics-playground-config
  labels:
    app.kubernetes.io/name: robotics-playground
    app.kubernetes.io/part-of: robotics-playground
data:
  config.yaml: |
    server:
      host: "0.0.0.0"
      port: 8000
      log_level: "info"

    rerun:
      grpc_port: 9876
      web_port: 9090

    bridge:
      type: "mock"
```

- [ ] **Step 3: Update Kustomize backend deployment**

Replace `deploy/kustomize/backend-deployment.yaml`:

```yaml
apiVersion: apps/v1
kind: Deployment
metadata:
  name: robotics-playground-backend
  labels:
    app.kubernetes.io/name: robotics-playground-backend
    app.kubernetes.io/component: backend
    app.kubernetes.io/part-of: robotics-playground
spec:
  replicas: 1
  selector:
    matchLabels:
      app.kubernetes.io/name: robotics-playground-backend
  template:
    metadata:
      labels:
        app.kubernetes.io/name: robotics-playground-backend
        app.kubernetes.io/component: backend
        app.kubernetes.io/part-of: robotics-playground
    spec:
      containers:
        - name: api
          image: quay.io/redhat-et/robotics-playground:latest
          ports:
            - name: http
              containerPort: 8000
              protocol: TCP
          env:
            - name: PLAYGROUND_CONFIG
              value: /etc/robotics-playground/config.yaml
          volumeMounts:
            - name: config
              mountPath: /etc/robotics-playground
              readOnly: true
          readinessProbe:
            httpGet:
              path: /api/health
              port: http
            initialDelaySeconds: 3
            periodSeconds: 10
          resources:
            requests:
              cpu: 50m
              memory: 128Mi
            limits:
              memory: 512Mi
      volumes:
        - name: config
          configMap:
            name: robotics-playground-config
```

- [ ] **Step 4: Update kustomization.yaml**

Replace `deploy/kustomize/kustomization.yaml`:

```yaml
apiVersion: kustomize.config.k8s.io/v1beta1
kind: Kustomization

resources:
  - ui-deployment.yaml
  - ui-service.yaml
  - backend-deployment.yaml
  - backend-service.yaml
  - configmap.yaml
```

- [ ] **Step 5: Update Makefile for profile support**

Add to `Makefile` (update the compose-up target and add compose-up-full):

```makefile
COMPOSE_PROFILES ?=

## Start Podman Compose stack
compose-up:
 podman compose -f deploy/compose.yaml $(if $(COMPOSE_PROFILES),--profile $(COMPOSE_PROFILES)) up -d

## Stop Podman Compose stack
compose-down:
 podman compose -f deploy/compose.yaml down
```

- [ ] **Step 6: Validate Kustomize manifests**

Run: `make validate`
Expected: kubeconform passes with no errors

- [ ] **Step 7: Build and test full stack**

Run:

```bash
make build
make compose-up
sleep 5
curl http://localhost:8080
curl http://localhost:8000/api/health
make compose-down
```

Expected: Both services start, health check returns ok, UI is accessible.

- [ ] **Step 8: Commit**

```bash
git add deploy/ Makefile
git commit -m "feat(deploy): add ConfigMap, Isaac Sim profile, and config volume mounts"
```

---

### Task 8: Clean Up Legacy Mock Files

**Files:**

- Delete: `backend/src/robotics_playground/mock_robot.py`
- Delete: `backend/tests/test_mock_robot.py`

**Interfaces:**

- Consumes: nothing (cleanup only)
- Produces: nothing — removes dead code

- [ ] **Step 1: Verify no imports remain**

Run:

```bash
cd backend && grep -r "mock_robot" src/ tests/
```

Expected: No results (all references should have been replaced in Task 3)

- [ ] **Step 2: Delete legacy files**

```bash
rm backend/src/robotics_playground/mock_robot.py
rm backend/tests/test_mock_robot.py
```

- [ ] **Step 3: Run all tests**

Run: `make test`
Expected: All pass

- [ ] **Step 4: Commit**

```bash
git add -u backend/
git commit -m "chore: remove legacy mock_robot module replaced by MockBridge"
```

---

### Task 9: End-to-End Verification

**Files:** None (verification only)

- [ ] **Step 1: Run full lint**

Run: `make lint`
Expected: All pass

- [ ] **Step 2: Run full test suite**

Run: `make test`
Expected: All pass

- [ ] **Step 3: Build container images**

Run: `make build`
Expected: Both images build successfully

- [ ] **Step 4: Run Podman Compose stack**

Run:

```bash
make compose-up
sleep 5
```

- [ ] **Step 5: Verify health endpoint**

Run: `curl http://localhost:8000/api/health`
Expected: `{"status":"ok"}`

- [ ] **Step 6: Verify WebSocket with bridge_status**

Run:

```python
# Quick Python test
import asyncio, websockets, json
async def test():
    async with websockets.connect("ws://localhost:8000/ws/sessions/test") as ws:
        msg = json.loads(await ws.recv())
        print(msg)
        assert msg["bridge_status"] == "mock"
        print("OK: bridge_status present")
asyncio.run(test())
```

Expected: Status message includes `bridge_status: "mock"`

- [ ] **Step 7: Verify frontend loads**

Open `http://localhost:8080` in browser. Verify:

- Speed slider visible in Simulation Control panel
- Bridge status label shows "Mock" in grey
- Play/Pause/Stop/Step/Reset buttons work as before
- Rerun viewer connects and shows mock data

- [ ] **Step 8: Stop stack**

Run: `make compose-down`

- [ ] **Step 9: Validate Kustomize**

Run: `make validate`
Expected: Pass

- [ ] **Step 10: Commit any fixes discovered during verification**

If any issues were found and fixed during steps 1-9, commit them:

```bash
git add -A
git commit -m "fix: address issues found during Phase 2 E2E verification"
```
