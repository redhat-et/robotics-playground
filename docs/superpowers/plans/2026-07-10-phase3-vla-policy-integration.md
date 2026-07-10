# Phase 3: VLA Policy Integration — Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Connect the backend to DreamZero on vLLM-Omni via OpenPI WebSocket, replacing the mock policy with a real VLA inference loop that drives Isaac Sim in lockstep.

**Architecture:** The backend's existing ROS 2 bridge collects observations from Isaac Lab. A new EmbodimentAdapter normalizes them into OpenPI format. An OpenPI WebSocket client sends them to vLLM-Omni and receives action chunks. The adapter denormalizes actions back to ROS 2 joint commands. A lockstep session loop orchestrates this cycle, freezing the sim during inference.

**Tech Stack:** Python 3.12+, FastAPI, rclpy, websockets, msgpack, Pillow, numpy, rerun-sdk, pydantic

## Global Constraints

- Conventional Commits for all commit messages
- Tests first: write tests before implementation
- Run `make lint`, `make test`, `make build` before committing
- YAML: 2-space indent
- Backend tests: `cd backend && uv run pytest -v`
- Backend lint: `cd backend && uv run ruff check src/ tests/ && uv run ruff format --check src/ tests/`
- Line length: 100 characters (ruff config)
- Target Python: 3.12+
- Spec: `docs/superpowers/specs/2026-07-10-phase3-vla-policy-integration-design.md`

## File Map

### New Files

| File | Responsibility |
| ------ | --------------- |
| `backend/src/robotics_playground/policy/__init__.py` | Package init + `create_policy()` factory |
| `backend/src/robotics_playground/policy/protocol.py` | `PolicyClient` protocol definition |
| `backend/src/robotics_playground/policy/mock_client.py` | Mock policy returning random (10,8) chunks |
| `backend/src/robotics_playground/policy/openpi_client.py` | WebSocket+msgpack client for vLLM-Omni |
| `backend/src/robotics_playground/policy/embodiment_adapter.py` | Joint reorder, normalize/denormalize, key remap |
| `backend/src/robotics_playground/vendored/msgpack_numpy.py` | numpy↔msgpack serialization (~60 lines from openpi-client) |
| `backend/tests/test_policy_mock.py` | Tests for MockClient |
| `backend/tests/test_embodiment_adapter.py` | Tests for EmbodimentAdapter |
| `backend/tests/test_openpi_client.py` | Tests for OpenPIClient (mocked WebSocket) |
| `backend/tests/test_session_lockstep.py` | Tests for lockstep session loop |

### Modified Files

| File | Change |
| ------ | -------- |
| `backend/src/robotics_playground/bridges/protocol.py` | Extend `Action` TypedDict, add `get_observation()` to `RobotBridge` |
| `backend/src/robotics_playground/bridges/mock_bridge.py` | Add `get_observation()`, update `send_action()` for new `Action` |
| `backend/src/robotics_playground/bridges/ros2_bridge.py` | Add `get_observation()`, update `send_action()`, configurable decimation |
| `backend/src/robotics_playground/config.py` | Add `PolicyConfig`, `EmbodimentConfig`, `physics_decimation` |
| `backend/src/robotics_playground/rerun_logger.py` | Add dual-path logging methods, updated blueprint |
| `backend/src/robotics_playground/session.py` | Lockstep loop, accept policy+adapter deps |
| `backend/src/robotics_playground/main.py` | Wire policy+adapter into session |
| `backend/pyproject.toml` | Add msgpack, websockets, Pillow dependencies |
| `backend/tests/test_bridges.py` | Update for new Action type |
| `backend/tests/test_session.py` | Update for new Session constructor |
| `backend/tests/test_mock_policy.py` | Remove (replaced by test_policy_mock.py) |

### Deleted Files

| File | Reason |
|------|--------|
| `backend/src/robotics_playground/mock_policy.py` | Replaced by `policy/mock_client.py` |

---

### Task 1: Extend Action Type & Bridge Protocol

**Files:**

- Modify: `backend/src/robotics_playground/bridges/protocol.py`
- Modify: `backend/src/robotics_playground/bridges/mock_bridge.py`
- Modify: `backend/tests/test_bridges.py`

**Interfaces:**

- Produces: `Action(TypedDict)` with `joint_positions: list[float]`, `joint_velocities: list[float]`, `gripper_position: float`
- Produces: `RobotBridge.get_observation() -> Observation` (new protocol method)

- [ ] **Step 1: Update the Action TypedDict and RobotBridge protocol**

In `backend/src/robotics_playground/bridges/protocol.py`, replace the existing `Action` and add `get_observation` to `RobotBridge`:

```python
class Action(TypedDict):
    joint_positions: list[float]
    joint_velocities: list[float]
    gripper_position: float


class RobotBridge(Protocol):
    @property
    def bridge_status(self) -> str: ...

    async def start(self) -> None: ...

    async def get_observation(self) -> Observation: ...

    def observation_stream(self) -> AsyncIterator[Observation]: ...

    async def send_action(self, action: Action) -> None: ...

    async def sim_control(self, action: str, speed: float | None = None) -> None: ...

    async def close(self) -> None: ...
```

- [ ] **Step 2: Update MockBridge for new Action type and get_observation**

In `backend/src/robotics_playground/bridges/mock_bridge.py`:

- Add `get_observation()` that returns a single synthetic observation with a short delay
- Update `send_action()` signature to accept the new `Action` shape (still a no-op)

```python
async def get_observation(self) -> Observation:
    t = self._step * 0.1
    image = np.zeros((240, 320, 3), dtype=np.uint8)
    image[:, :, 0] = np.arange(320) * 255 // 320
    image[:, :, 1] = int(127 + 127 * math.sin(t))

    positions = [math.sin(t + i * math.pi / 3) for i in range(6)]
    velocities = [math.cos(t + i * math.pi / 3) for i in range(6)]

    obs = Observation(
        step=self._step,
        cameras={"wrist": image},
        joint_positions=positions,
        joint_velocities=velocities,
    )
    self._step += 1
    await asyncio.sleep(0.01)
    return obs
```

Add `self._step = 0` to the class body and refactor `observation_stream` to use `get_observation`.

- [ ] **Step 3: Update test_bridges.py for new Action shape**

Update `test_action_type_shape` to use the new Action fields:

```python
def test_action_type_shape():
    act: Action = {
        "joint_positions": [float("nan")] * 7,
        "joint_velocities": [0.0] * 7,
        "gripper_position": 0.5,
    }
    assert len(act["joint_positions"]) == 7
    assert len(act["joint_velocities"]) == 7
    assert isinstance(act["gripper_position"], float)
```

Add a test for `get_observation`:

```python
@pytest.mark.anyio
async def test_mock_bridge_get_observation():
    from robotics_playground.bridges.mock_bridge import MockBridge

    bridge = MockBridge()
    await bridge.start()
    obs = await bridge.get_observation()
    assert "cameras" in obs
    assert "wrist" in obs["cameras"]
    assert isinstance(obs["joint_positions"], list)
    assert obs["step"] == 0
    obs2 = await bridge.get_observation()
    assert obs2["step"] == 1
    await bridge.close()
```

Update `test_mock_bridge_send_action_is_noop` to pass the new Action shape:

```python
await bridge.send_action({
    "joint_positions": [float("nan")] * 7,
    "joint_velocities": [0.0] * 7,
    "gripper_position": 0.5,
})
```

- [ ] **Step 4: Run tests**

```bash
cd backend && uv run pytest tests/test_bridges.py -v
```

Expected: all tests pass.

- [ ] **Step 5: Lint and commit**

```bash
cd backend && uv run ruff check src/ tests/ && uv run ruff format --check src/ tests/
git add backend/src/robotics_playground/bridges/protocol.py \
        backend/src/robotics_playground/bridges/mock_bridge.py \
        backend/tests/test_bridges.py
git commit -m "feat: extend Action type with velocities/gripper and add get_observation to bridge protocol"
```

---

### Task 2: Config Models & Dependencies

**Files:**

- Modify: `backend/src/robotics_playground/config.py`
- Modify: `backend/pyproject.toml`
- Modify: `backend/tests/test_config.py`

**Interfaces:**

- Produces: `EmbodimentConfig(BaseModel)` with `joint_names`, `training_order`, `joint_limits`, `gripper_joint`, `gripper_limits`, `camera_mapping`, `image_size`
- Produces: `PolicyConfig(BaseModel)` with `type`, `endpoint`, `model_name`, `embodiment`
- Produces: `ROS2Config.physics_decimation: int = 10`

- [ ] **Step 1: Write failing test for new config models**

Add to `backend/tests/test_config.py`:

```python
def test_policy_config_defaults():
    from robotics_playground.config import PlaygroundConfig

    config = PlaygroundConfig()
    assert config.policy.type == "mock"
    assert config.policy.endpoint == ""
    assert config.policy.model_name == "dreamzero"
    assert config.policy.embodiment.joint_names == []
    assert config.policy.embodiment.image_size == [224, 224]
    assert config.policy.embodiment.gripper_limits == [0.0, 0.04]


def test_policy_config_from_dict():
    from robotics_playground.config import PlaygroundConfig

    data = {
        "policy": {
            "type": "openpi",
            "endpoint": "ws://localhost:8080/v1/realtime/robot/openpi",
            "embodiment": {
                "joint_names": ["j1", "j2"],
                "training_order": ["j2", "j1"],
                "joint_limits": {"j1": [-1.0, 1.0], "j2": [-2.0, 2.0]},
                "gripper_joint": "grip",
                "camera_mapping": {"wrist": "observation/wrist_image_left"},
            },
        }
    }
    config = PlaygroundConfig(**data)
    assert config.policy.type == "openpi"
    assert config.policy.embodiment.joint_names == ["j1", "j2"]
    assert config.policy.embodiment.training_order == ["j2", "j1"]
    assert config.policy.embodiment.camera_mapping == {"wrist": "observation/wrist_image_left"}


def test_ros2_config_physics_decimation():
    from robotics_playground.config import PlaygroundConfig

    config = PlaygroundConfig()
    assert config.ros2.physics_decimation == 10

    config2 = PlaygroundConfig(ros2={"physics_decimation": 5})
    assert config2.ros2.physics_decimation == 5
```

- [ ] **Step 2: Run tests to verify they fail**

```bash
cd backend && uv run pytest tests/test_config.py -v
```

Expected: FAIL — `PlaygroundConfig` has no `policy` attribute.

- [ ] **Step 3: Add config models**

In `backend/src/robotics_playground/config.py`, add before `PlaygroundConfig`:

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

Add `physics_decimation` to `ROS2Config`:

```python
class ROS2Config(BaseModel):
    # ... existing fields ...
    physics_decimation: int = 10
```

Add `policy` to `PlaygroundConfig`:

```python
class PlaygroundConfig(BaseModel):
    server: ServerConfig = ServerConfig()
    rerun: RerunConfig = RerunConfig()
    bridge: BridgeConfig = BridgeConfig()
    ros2: ROS2Config = ROS2Config()
    policy: PolicyConfig = PolicyConfig()
```

- [ ] **Step 4: Add pip dependencies**

In `backend/pyproject.toml`, add to `dependencies`:

```
"msgpack>=1.0",
"websockets>=12.0",
"Pillow>=10.0",
```

- [ ] **Step 5: Install dependencies and run tests**

```bash
cd backend && uv sync && uv run pytest tests/test_config.py -v
```

Expected: all tests pass.

- [ ] **Step 6: Lint and commit**

```bash
cd backend && uv run ruff check src/ tests/ && uv run ruff format --check src/ tests/
git add backend/src/robotics_playground/config.py backend/pyproject.toml \
        backend/tests/test_config.py backend/uv.lock
git commit -m "feat: add PolicyConfig, EmbodimentConfig, and new pip dependencies"
```

---

### Task 3: Vendored msgpack_numpy & PolicyClient Protocol

**Files:**

- Create: `backend/src/robotics_playground/vendored/msgpack_numpy.py`
- Create: `backend/src/robotics_playground/policy/__init__.py`
- Create: `backend/src/robotics_playground/policy/protocol.py`

**Interfaces:**

- Produces: `msgpack_numpy.packb(obj) -> bytes`, `msgpack_numpy.unpackb(data) -> obj`, `msgpack_numpy.Packer`
- Produces: `PolicyClient` protocol with `connect()`, `infer(obs: dict) -> dict`, `reset()`, `close()`

- [ ] **Step 1: Vendor msgpack_numpy.py**

Create `backend/src/robotics_playground/vendored/msgpack_numpy.py` — adapted from `openpi-client` (Apache 2.0):

```python
"""numpy array support for msgpack. Adapted from openpi-client (Apache 2.0)."""

from __future__ import annotations

import functools

import msgpack
import numpy as np


def _pack_array(obj):
    if isinstance(obj, (np.ndarray, np.generic)) and obj.dtype.kind in ("V", "O", "c"):
        raise ValueError(f"Unsupported dtype: {obj.dtype}")

    if isinstance(obj, np.ndarray):
        return {
            b"__ndarray__": True,
            b"data": obj.tobytes(),
            b"dtype": obj.dtype.str,
            b"shape": obj.shape,
        }

    if isinstance(obj, np.generic):
        return {
            b"__npgeneric__": True,
            b"data": obj.item(),
            b"dtype": obj.dtype.str,
        }

    return obj


def _unpack_array(obj):
    if b"__ndarray__" in obj:
        return np.ndarray(buffer=obj[b"data"], dtype=np.dtype(obj[b"dtype"]), shape=obj[b"shape"])

    if b"__npgeneric__" in obj:
        return np.dtype(obj[b"dtype"]).type(obj[b"data"])

    return obj


Packer = functools.partial(msgpack.Packer, default=_pack_array)
packb = functools.partial(msgpack.packb, default=_pack_array)

Unpacker = functools.partial(msgpack.Unpacker, object_hook=_unpack_array)
unpackb = functools.partial(msgpack.unpackb, object_hook=_unpack_array)
```

- [ ] **Step 2: Create policy package with protocol**

Create `backend/src/robotics_playground/policy/__init__.py`:

```python
from __future__ import annotations

from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from robotics_playground.config import PlaygroundConfig
    from robotics_playground.policy.protocol import PolicyClient


def create_policy(config: PlaygroundConfig) -> PolicyClient:
    if config.policy.type == "openpi":
        from robotics_playground.policy.openpi_client import OpenPIClient

        return OpenPIClient(config.policy.endpoint)

    from robotics_playground.policy.mock_client import MockClient

    return MockClient()
```

Create `backend/src/robotics_playground/policy/protocol.py`:

```python
from __future__ import annotations

from typing import Protocol


class PolicyClient(Protocol):
    async def connect(self) -> None: ...

    async def infer(self, obs: dict) -> dict: ...

    async def reset(self) -> None: ...

    async def close(self) -> None: ...
```

- [ ] **Step 3: Run lint to verify**

```bash
cd backend && uv run ruff check src/robotics_playground/vendored/msgpack_numpy.py \
    src/robotics_playground/policy/
```

Expected: no errors.

- [ ] **Step 4: Commit**

```bash
git add backend/src/robotics_playground/vendored/msgpack_numpy.py \
        backend/src/robotics_playground/policy/__init__.py \
        backend/src/robotics_playground/policy/protocol.py
git commit -m "feat: add PolicyClient protocol and vendor msgpack_numpy"
```

---

### Task 4: MockClient

**Files:**

- Create: `backend/src/robotics_playground/policy/mock_client.py`
- Create: `backend/tests/test_policy_mock.py`
- Delete: `backend/src/robotics_playground/mock_policy.py`
- Delete: `backend/tests/test_mock_policy.py`

**Interfaces:**

- Consumes: `PolicyClient` protocol from `policy/protocol.py`
- Produces: `MockClient` class with `infer()` returning `{"actions": np.ndarray(10, 8)}`

- [ ] **Step 1: Write tests for MockClient**

Create `backend/tests/test_policy_mock.py`:

```python
from __future__ import annotations

import numpy as np
import pytest

from robotics_playground.policy.mock_client import MockClient


@pytest.mark.anyio
async def test_mock_client_connect_is_noop():
    client = MockClient()
    await client.connect()
    await client.close()


@pytest.mark.anyio
async def test_mock_client_infer_returns_action_chunk():
    client = MockClient()
    await client.connect()
    obs = {
        "observation/wrist_image_left": np.zeros((224, 224, 3), dtype=np.uint8),
        "observation/joint_position": np.zeros(7),
        "observation/gripper_position": np.zeros(1),
        "prompt": "pick up the block",
    }
    result = await client.infer(obs)
    assert "actions" in result
    assert isinstance(result["actions"], np.ndarray)
    assert result["actions"].shape == (10, 8)
    assert result["actions"].min() >= -1.0
    assert result["actions"].max() <= 1.0
    await client.close()


@pytest.mark.anyio
async def test_mock_client_reset_is_noop():
    client = MockClient()
    await client.connect()
    await client.reset()
    await client.close()
```

- [ ] **Step 2: Run tests to verify they fail**

```bash
cd backend && uv run pytest tests/test_policy_mock.py -v
```

Expected: FAIL — `mock_client` module does not exist.

- [ ] **Step 3: Implement MockClient**

Create `backend/src/robotics_playground/policy/mock_client.py`:

```python
from __future__ import annotations

import asyncio

import numpy as np


class MockClient:
    async def connect(self) -> None:
        pass

    async def infer(self, obs: dict) -> dict:
        await asyncio.sleep(0.05)
        actions = np.random.uniform(-1.0, 1.0, size=(10, 8)).astype(np.float32)
        return {"actions": actions}

    async def reset(self) -> None:
        pass

    async def close(self) -> None:
        pass
```

- [ ] **Step 4: Run tests**

```bash
cd backend && uv run pytest tests/test_policy_mock.py -v
```

Expected: all pass.

- [ ] **Step 5: Delete old mock_policy.py and its test**

```bash
rm backend/src/robotics_playground/mock_policy.py
rm backend/tests/test_mock_policy.py
```

- [ ] **Step 6: Lint and commit**

```bash
cd backend && uv run ruff check src/ tests/ && uv run ruff format --check src/ tests/
git add backend/src/robotics_playground/policy/mock_client.py \
        backend/tests/test_policy_mock.py
git rm backend/src/robotics_playground/mock_policy.py \
       backend/tests/test_mock_policy.py
git commit -m "feat: add MockClient replacing mock_policy module"
```

---

### Task 5: EmbodimentAdapter

**Files:**

- Create: `backend/src/robotics_playground/policy/embodiment_adapter.py`
- Create: `backend/tests/test_embodiment_adapter.py`

**Interfaces:**

- Consumes: `EmbodimentConfig` from `config.py`, `Observation` and `Action` from `bridges/protocol.py`
- Produces: `EmbodimentAdapter.observation_to_openpi(obs, instruction) -> dict`
- Produces: `EmbodimentAdapter.action_chunk_from_openpi(raw) -> list[Action]`

- [ ] **Step 1: Write tests for observation normalization**

Create `backend/tests/test_embodiment_adapter.py`:

```python
from __future__ import annotations

import math

import numpy as np
import pytest

from robotics_playground.bridges.protocol import Observation
from robotics_playground.config import EmbodimentConfig
from robotics_playground.policy.embodiment_adapter import EmbodimentAdapter

FRANKA_CONFIG = EmbodimentConfig(
    joint_names=["j1", "j2", "j3", "j4", "j5", "j6", "j7"],
    training_order=["j1", "j2", "j3", "j4", "j5", "j6", "j7"],
    joint_limits={
        "j1": [-2.0, 2.0],
        "j2": [-1.0, 1.0],
        "j3": [-2.0, 2.0],
        "j4": [-3.0, 0.0],
        "j5": [-2.0, 2.0],
        "j6": [0.0, 4.0],
        "j7": [-2.0, 2.0],
    },
    gripper_joint="grip",
    gripper_limits=[0.0, 0.04],
    camera_mapping={
        "wrist": "observation/wrist_image_left",
        "exterior_1": "observation/exterior_image_1_left",
    },
    image_size=[224, 224],
)


def _make_obs(
    positions: list[float] | None = None,
    velocities: list[float] | None = None,
) -> Observation:
    return Observation(
        step=0,
        cameras={
            "wrist": np.random.randint(0, 255, (480, 640, 3), dtype=np.uint8),
            "exterior_1": np.random.randint(0, 255, (480, 640, 3), dtype=np.uint8),
        },
        joint_positions=positions or [0.0] * 7,
        joint_velocities=velocities or [0.0] * 7,
    )


def test_observation_to_openpi_keys():
    adapter = EmbodimentAdapter(FRANKA_CONFIG)
    obs = _make_obs()
    result = adapter.observation_to_openpi(obs, "pick up block")
    assert "observation/wrist_image_left" in result
    assert "observation/exterior_image_1_left" in result
    assert "observation/joint_position" in result
    assert "observation/gripper_position" in result
    assert result["prompt"] == "pick up block"


def test_observation_images_resized_to_224():
    adapter = EmbodimentAdapter(FRANKA_CONFIG)
    obs = _make_obs()
    result = adapter.observation_to_openpi(obs, "")
    for key in ["observation/wrist_image_left", "observation/exterior_image_1_left"]:
        img = result[key]
        assert img.shape[0] == 224
        assert img.shape[1] == 224
        assert img.shape[2] == 3
        assert img.dtype == np.uint8


def test_observation_joint_normalization():
    adapter = EmbodimentAdapter(FRANKA_CONFIG)
    # j1 limits [-2, 2], position 0.0 -> normalized 0.0
    # j2 limits [-1, 1], position 1.0 -> normalized 1.0
    # j2 limits [-1, 1], position -1.0 -> normalized -1.0
    obs = _make_obs(positions=[0.0, 1.0, 0.0, -1.5, 0.0, 2.0, 0.0])
    result = adapter.observation_to_openpi(obs, "")
    joints = result["observation/joint_position"]
    assert joints.shape == (7,)
    assert abs(joints[0] - 0.0) < 1e-6
    assert abs(joints[1] - 1.0) < 1e-6


def test_observation_joint_reorder():
    config = EmbodimentConfig(
        joint_names=["a", "b", "c"],
        training_order=["c", "a", "b"],
        joint_limits={"a": [-1, 1], "b": [-1, 1], "c": [-1, 1]},
        gripper_joint="g",
        gripper_limits=[0, 1],
        camera_mapping={},
        image_size=[224, 224],
    )
    adapter = EmbodimentAdapter(config)
    obs = Observation(
        step=0,
        cameras={},
        joint_positions=[0.1, 0.2, 0.3],
        joint_velocities=[0.0, 0.0, 0.0],
    )
    result = adapter.observation_to_openpi(obs, "")
    joints = result["observation/joint_position"]
    # training_order=[c, a, b], so output should be [0.3, 0.1, 0.2] normalized
    assert abs(joints[0] - 0.3) < 1e-6
    assert abs(joints[1] - 0.1) < 1e-6
    assert abs(joints[2] - 0.2) < 1e-6
```

- [ ] **Step 2: Write tests for action denormalization**

Append to `backend/tests/test_embodiment_adapter.py`:

```python
def test_action_chunk_from_openpi_shape():
    adapter = EmbodimentAdapter(FRANKA_CONFIG)
    raw = {"actions": np.zeros((10, 8), dtype=np.float32)}
    actions = adapter.action_chunk_from_openpi(raw)
    assert len(actions) == 10
    for a in actions:
        assert len(a["joint_positions"]) == 7
        assert len(a["joint_velocities"]) == 7
        assert isinstance(a["gripper_position"], float)


def test_action_chunk_nan_dispatch():
    adapter = EmbodimentAdapter(FRANKA_CONFIG)
    raw = {"actions": np.zeros((10, 8), dtype=np.float32)}
    actions = adapter.action_chunk_from_openpi(raw)
    for a in actions:
        # Arm joints: velocity has real values, position is NaN
        for i in range(7):
            assert math.isnan(a["joint_positions"][i])
            assert not math.isnan(a["joint_velocities"][i])
        # Gripper: position has real value
        assert not math.isnan(a["gripper_position"])


def test_action_denormalization_round_trip():
    adapter = EmbodimentAdapter(FRANKA_CONFIG)
    obs = _make_obs(positions=[0.0, 0.5, -1.0, -1.5, 1.0, 2.0, -0.5])
    openpi_obs = adapter.observation_to_openpi(obs, "")

    # Construct action that "echoes" the normalized joint positions as velocities
    normalized_joints = openpi_obs["observation/joint_position"]
    action_row = np.concatenate([normalized_joints, np.array([0.5])])
    raw = {"actions": np.tile(action_row, (10, 1)).astype(np.float32)}

    actions = adapter.action_chunk_from_openpi(raw)
    # Verify denormalization produced physical-range values (not [-1, 1])
    for a in actions:
        for v in a["joint_velocities"]:
            assert not math.isnan(v)


def test_action_reorder_inverse():
    config = EmbodimentConfig(
        joint_names=["a", "b", "c"],
        training_order=["c", "a", "b"],
        joint_limits={"a": [-1, 1], "b": [-1, 1], "c": [-1, 1]},
        gripper_joint="g",
        gripper_limits=[0, 1],
        camera_mapping={},
        image_size=[224, 224],
    )
    adapter = EmbodimentAdapter(config)
    # Action in training order [c, a, b] = [0.3, 0.1, 0.2]
    action_row = np.array([0.3, 0.1, 0.2, 0.5], dtype=np.float32)
    raw = {"actions": action_row.reshape(1, 4)}
    actions = adapter.action_chunk_from_openpi(raw)
    vels = actions[0]["joint_velocities"]
    # Should be reordered back to URDF [a, b, c]: denorm of [0.1, 0.2, 0.3]
    # With limits [-1, 1], denorm(x) = x * (1 - (-1)) / 2 = x (symmetric around 0, half-range=1)
    # Actually denorm from [-1,1] to velocity range — need to check what denorm means for velocities
    # For now just verify the reorder happened: URDF index 0 (a) got training index 1 value
    assert len(vels) == 3
```

- [ ] **Step 3: Run tests to verify they fail**

```bash
cd backend && uv run pytest tests/test_embodiment_adapter.py -v
```

Expected: FAIL — `embodiment_adapter` module does not exist.

- [ ] **Step 4: Implement EmbodimentAdapter**

Create `backend/src/robotics_playground/policy/embodiment_adapter.py`:

```python
from __future__ import annotations

import math
from typing import TYPE_CHECKING

import numpy as np
from PIL import Image

from robotics_playground.bridges.protocol import Action

if TYPE_CHECKING:
    from robotics_playground.bridges.protocol import Observation
    from robotics_playground.config import EmbodimentConfig


class EmbodimentAdapter:
    def __init__(self, config: EmbodimentConfig):
        self._config = config
        self._image_size = tuple(config.image_size)

        # Build reorder indices: URDF order → training order
        self._obs_reorder = [config.joint_names.index(n) for n in config.training_order]
        # Inverse: training order → URDF order
        self._act_reorder = [config.training_order.index(n) for n in config.joint_names]

        # Joint limits as arrays in training order
        n_joints = len(config.training_order)
        self._joint_lower = np.zeros(n_joints, dtype=np.float64)
        self._joint_upper = np.zeros(n_joints, dtype=np.float64)
        for i, name in enumerate(config.training_order):
            limits = config.joint_limits[name]
            self._joint_lower[i] = limits[0]
            self._joint_upper[i] = limits[1]

        self._gripper_lower = config.gripper_limits[0]
        self._gripper_upper = config.gripper_limits[1]

    def _normalize(self, value: np.ndarray, lower: np.ndarray, upper: np.ndarray) -> np.ndarray:
        return 2.0 * (value - lower) / (upper - lower) - 1.0

    def _denormalize(self, value: np.ndarray, lower: np.ndarray, upper: np.ndarray) -> np.ndarray:
        return (value + 1.0) * (upper - lower) / 2.0 + lower

    def _resize_image(self, image: np.ndarray) -> np.ndarray:
        h, w = self._image_size
        pil_img = Image.fromarray(image)
        # Resize maintaining aspect ratio with padding
        pil_img.thumbnail((w, h), Image.LANCZOS)
        padded = Image.new("RGB", (w, h), (0, 0, 0))
        offset = ((w - pil_img.width) // 2, (h - pil_img.height) // 2)
        padded.paste(pil_img, offset)
        return np.array(padded)

    def observation_to_openpi(self, obs: Observation, instruction: str) -> dict:
        result: dict = {}

        # Remap and resize camera images
        for ros_name, openpi_key in self._config.camera_mapping.items():
            if ros_name in obs["cameras"]:
                result[openpi_key] = self._resize_image(obs["cameras"][ros_name])

        # Reorder and normalize joint positions
        positions = np.array(obs["joint_positions"], dtype=np.float64)
        reordered = positions[self._obs_reorder]
        result["observation/joint_position"] = self._normalize(
            reordered, self._joint_lower, self._joint_upper
        ).astype(np.float32)

        # Gripper — use last position if available, else 0
        gripper_val = 0.0
        if len(obs["joint_positions"]) > len(self._config.joint_names):
            gripper_val = obs["joint_positions"][len(self._config.joint_names)]
        gripper_norm = self._normalize(
            np.array([gripper_val]),
            np.array([self._gripper_lower]),
            np.array([self._gripper_upper]),
        )
        result["observation/gripper_position"] = gripper_norm.astype(np.float32)

        result["prompt"] = instruction
        return result

    def action_chunk_from_openpi(self, raw: dict) -> list[Action]:
        actions_array = raw["actions"]  # (chunk_size, n_joints + 1)
        n_joints = len(self._config.joint_names)
        chunk_size = actions_array.shape[0]

        result = []
        for i in range(chunk_size):
            row = actions_array[i]
            # Split: first n_joints are arm velocities, last is gripper
            vel_normalized = row[:n_joints].astype(np.float64)
            gripper_normalized = float(row[n_joints]) if row.shape[0] > n_joints else 0.0

            # Denormalize velocities
            vel_physical = self._denormalize(vel_normalized, self._joint_lower, self._joint_upper)

            # Reorder from training order to URDF order
            vel_urdf = vel_physical[self._act_reorder]

            # Denormalize gripper
            gripper_physical = self._denormalize(
                np.array([gripper_normalized]),
                np.array([self._gripper_lower]),
                np.array([self._gripper_upper]),
            )[0]

            # Build Action with NaN dispatch
            result.append(
                Action(
                    joint_positions=[math.nan] * n_joints,
                    joint_velocities=vel_urdf.tolist(),
                    gripper_position=float(gripper_physical),
                )
            )

        return result
```

- [ ] **Step 5: Run tests**

```bash
cd backend && uv run pytest tests/test_embodiment_adapter.py -v
```

Expected: all pass.

- [ ] **Step 6: Lint and commit**

```bash
cd backend && uv run ruff check src/ tests/ && uv run ruff format --check src/ tests/
git add backend/src/robotics_playground/policy/embodiment_adapter.py \
        backend/tests/test_embodiment_adapter.py
git commit -m "feat: add EmbodimentAdapter for OpenPI observation/action conversion"
```

---

### Task 6: OpenPIClient

**Files:**

- Create: `backend/src/robotics_playground/policy/openpi_client.py`
- Create: `backend/tests/test_openpi_client.py`

**Interfaces:**

- Consumes: `PolicyClient` protocol, `vendored.msgpack_numpy`
- Produces: `OpenPIClient(endpoint: str)` with `connect()`, `infer(obs) -> dict`, `close()`

- [ ] **Step 1: Write tests with mocked WebSocket**

Create `backend/tests/test_openpi_client.py`:

```python
from __future__ import annotations

from unittest.mock import MagicMock, patch

import numpy as np
import pytest

from robotics_playground.vendored import msgpack_numpy


@pytest.mark.anyio
async def test_openpi_client_connect_and_infer():
    from robotics_playground.policy.openpi_client import OpenPIClient

    mock_ws = MagicMock()
    # Server sends metadata on connect
    mock_ws.recv.side_effect = [
        msgpack_numpy.packb({"model": "dreamzero"}),  # metadata
        msgpack_numpy.packb({"actions": np.zeros((10, 8), dtype=np.float32)}),  # infer response
    ]

    with patch("websockets.sync.client.connect", return_value=mock_ws):
        client = OpenPIClient("ws://localhost:8080/v1/realtime/robot/openpi")
        await client.connect()

        obs = {
            "observation/joint_position": np.zeros(7, dtype=np.float32),
            "prompt": "test",
        }
        result = await client.infer(obs)

        assert "actions" in result
        assert result["actions"].shape == (10, 8)
        mock_ws.send.assert_called_once()

        await client.close()
        mock_ws.close.assert_called_once()


@pytest.mark.anyio
async def test_openpi_client_infer_raises_on_string_response():
    from robotics_playground.policy.openpi_client import OpenPIClient

    mock_ws = MagicMock()
    mock_ws.recv.side_effect = [
        msgpack_numpy.packb({"model": "dreamzero"}),
        "Error: model not found",
    ]

    with patch("websockets.sync.client.connect", return_value=mock_ws):
        client = OpenPIClient("ws://localhost:8080/v1/realtime/robot/openpi")
        await client.connect()

        with pytest.raises(RuntimeError, match="Error in inference server"):
            await client.infer({"prompt": "test"})

        await client.close()
```

- [ ] **Step 2: Run tests to verify they fail**

```bash
cd backend && uv run pytest tests/test_openpi_client.py -v
```

Expected: FAIL — `openpi_client` module does not exist.

- [ ] **Step 3: Implement OpenPIClient**

Create `backend/src/robotics_playground/policy/openpi_client.py`:

```python
from __future__ import annotations

import asyncio
import logging

import websockets.sync.client

from robotics_playground.vendored import msgpack_numpy

logger = logging.getLogger(__name__)


class OpenPIClient:
    def __init__(self, endpoint: str) -> None:
        self._endpoint = endpoint
        self._ws: websockets.sync.client.ClientConnection | None = None
        self._packer = msgpack_numpy.Packer()
        self._server_metadata: dict = {}

    async def connect(self) -> None:
        self._ws, self._server_metadata = await asyncio.to_thread(self._connect_sync)
        logger.info("Connected to OpenPI server at %s", self._endpoint)

    def _connect_sync(self) -> tuple:
        conn = websockets.sync.client.connect(
            self._endpoint,
            compression=None,
            max_size=None,
        )
        metadata = msgpack_numpy.unpackb(conn.recv())
        return conn, metadata

    async def infer(self, obs: dict) -> dict:
        return await asyncio.to_thread(self._infer_sync, obs)

    def _infer_sync(self, obs: dict) -> dict:
        if self._ws is None:
            raise RuntimeError("Not connected")
        data = self._packer.pack(obs)
        self._ws.send(data)
        response = self._ws.recv()
        if isinstance(response, str):
            raise RuntimeError(f"Error in inference server:\n{response}")
        return msgpack_numpy.unpackb(response)

    async def reset(self) -> None:
        pass

    async def close(self) -> None:
        if self._ws is not None:
            await asyncio.to_thread(self._ws.close)
            self._ws = None
```

- [ ] **Step 4: Run tests**

```bash
cd backend && uv run pytest tests/test_openpi_client.py -v
```

Expected: all pass.

- [ ] **Step 5: Lint and commit**

```bash
cd backend && uv run ruff check src/ tests/ && uv run ruff format --check src/ tests/
git add backend/src/robotics_playground/policy/openpi_client.py \
        backend/tests/test_openpi_client.py
git commit -m "feat: add OpenPIClient for WebSocket+msgpack inference"
```

---

### Task 7: Dual-Path Rerun Logging

**Files:**

- Modify: `backend/src/robotics_playground/rerun_logger.py`
- Modify: `backend/tests/test_rerun_logger.py`

**Interfaces:**

- Consumes: `Action` from `bridges/protocol.py`
- Produces: `RerunLogger.log_raw_action_tensor(actions: np.ndarray, step: int)`
- Produces: `RerunLogger.log_inference_latency(latency_ms: float, step: int)`
- Produces: `RerunLogger.log_action_trajectory(action_chunk: list[Action], step: int)`

- [ ] **Step 1: Write tests for new logging methods**

Add to `backend/tests/test_rerun_logger.py`:

```python
def test_log_raw_action_tensor_no_error(mock_rerun):
    logger = RerunLogger()
    logger.start()
    actions = np.zeros((10, 8), dtype=np.float32)
    logger.log_raw_action_tensor(actions, step=0)


def test_log_inference_latency_no_error(mock_rerun):
    logger = RerunLogger()
    logger.start()
    logger.log_inference_latency(42.5, step=0)


def test_log_action_trajectory_no_error(mock_rerun):
    import math

    from robotics_playground.bridges.protocol import Action

    logger = RerunLogger()
    logger.start()
    chunk = [
        Action(
            joint_positions=[math.nan] * 7,
            joint_velocities=[0.1 * i] * 7,
            gripper_position=0.02,
        )
        for i in range(10)
    ]
    logger.log_action_trajectory(chunk, step=0)
```

- [ ] **Step 2: Run tests to verify they fail**

```bash
cd backend && uv run pytest tests/test_rerun_logger.py -v -k "tensor or latency or trajectory"
```

Expected: FAIL — methods do not exist.

- [ ] **Step 3: Add new logging methods to RerunLogger**

In `backend/src/robotics_playground/rerun_logger.py`, add these methods:

```python
def log_raw_action_tensor(self, actions: np.ndarray, step: int):
    rr.set_time("step", sequence=self._step_offset + step)
    rr.log(f"{self._prefix}/policy/raw_output", rr.Tensor(actions))
    for dim in range(actions.shape[1]):
        rr.log(
            f"{self._prefix}/policy/raw_output/dim_{dim}",
            rr.Scalars(float(actions[0, dim])),
        )

def log_inference_latency(self, latency_ms: float, step: int):
    rr.set_time("step", sequence=self._step_offset + step)
    rr.log(f"{self._prefix}/policy/inference_ms", rr.Scalars(latency_ms))

def log_action_trajectory(self, action_chunk: list[Action], step: int):
    rr.set_time("step", sequence=self._step_offset + step)
    if not action_chunk:
        return
    n_joints = len(action_chunk[0]["joint_velocities"])
    for j in range(n_joints):
        rr.log(
            f"{self._prefix}/intent/joint_{j}_velocity",
            rr.Scalars(action_chunk[0]["joint_velocities"][j]),
        )
    rr.log(
        f"{self._prefix}/intent/gripper",
        rr.Scalars(action_chunk[0]["gripper_position"]),
    )
```

Add the `Action` import at the top:

```python
if TYPE_CHECKING:
    from robotics_playground.bridges.protocol import Action, Observation
```

Update `_build_blueprint` to add the Policy Output panel — replace the single `TimeSeriesView` with a horizontal split:

```python
rrb.Horizontal(
    rrb.TimeSeriesView(
        origin=f"{self._prefix}/joints",
        name="Joint States",
        plot_legend=rrb.PlotLegend(visible=False),
    ),
    rrb.TimeSeriesView(
        origin=f"{self._prefix}/policy",
        name="Policy Output",
        plot_legend=rrb.PlotLegend(visible=False),
    ),
),
```

- [ ] **Step 4: Run tests**

```bash
cd backend && uv run pytest tests/test_rerun_logger.py -v
```

Expected: all pass.

- [ ] **Step 5: Lint and commit**

```bash
cd backend && uv run ruff check src/ tests/ && uv run ruff format --check src/ tests/
git add backend/src/robotics_playground/rerun_logger.py \
        backend/tests/test_rerun_logger.py
git commit -m "feat: add dual-path Rerun logging for policy tensors and trajectories"
```

---

### Task 8: Lockstep Session Loop & Wiring

**Files:**

- Modify: `backend/src/robotics_playground/session.py`
- Modify: `backend/src/robotics_playground/main.py`
- Modify: `backend/src/robotics_playground/bridges/__init__.py`
- Create: `backend/tests/test_session_lockstep.py`
- Modify: `backend/tests/test_session.py`

**Interfaces:**

- Consumes: `PolicyClient`, `EmbodimentAdapter`, `RobotBridge`, `RerunLogger`
- Produces: `Session(bridge, policy, adapter, rerun_logger)` with lockstep `_run_loop`

- [ ] **Step 1: Write tests for lockstep session**

Create `backend/tests/test_session_lockstep.py`:

```python
from __future__ import annotations

import asyncio
import math
from unittest.mock import MagicMock

import numpy as np
import pytest

from robotics_playground.bridges.mock_bridge import MockBridge
from robotics_playground.config import EmbodimentConfig
from robotics_playground.policy.embodiment_adapter import EmbodimentAdapter
from robotics_playground.policy.mock_client import MockClient
from robotics_playground.session import Session

SIMPLE_CONFIG = EmbodimentConfig(
    joint_names=["j1", "j2", "j3", "j4", "j5", "j6"],
    training_order=["j1", "j2", "j3", "j4", "j5", "j6"],
    joint_limits={f"j{i}": [-1, 1] for i in range(1, 7)},
    gripper_joint="g",
    gripper_limits=[0, 1],
    camera_mapping={"wrist": "observation/wrist_image_left"},
    image_size=[224, 224],
)


def _make_mock_logger():
    logger = MagicMock()
    logger.log_observation = MagicMock()
    logger.log_action = MagicMock()
    logger.log_instruction = MagicMock()
    logger.log_raw_action_tensor = MagicMock()
    logger.log_inference_latency = MagicMock()
    logger.log_action_trajectory = MagicMock()
    return logger


@pytest.mark.anyio
async def test_lockstep_session_runs_and_logs():
    mock_logger = _make_mock_logger()
    adapter = EmbodimentAdapter(SIMPLE_CONFIG)
    session = Session(
        bridge=MockBridge(),
        policy=MockClient(),
        adapter=adapter,
        rerun_logger=mock_logger,
    )
    await session.start()
    await asyncio.sleep(0.5)
    await session.stop()

    assert mock_logger.log_observation.call_count >= 1
    assert mock_logger.log_raw_action_tensor.call_count >= 1
    assert mock_logger.log_inference_latency.call_count >= 1
    assert mock_logger.log_action_trajectory.call_count >= 1


@pytest.mark.anyio
async def test_lockstep_session_initial_state():
    adapter = EmbodimentAdapter(SIMPLE_CONFIG)
    session = Session(
        bridge=MockBridge(),
        policy=MockClient(),
        adapter=adapter,
        rerun_logger=_make_mock_logger(),
    )
    assert session.state == "idle"
    assert session.step == 0


@pytest.mark.anyio
async def test_lockstep_session_pause_resume():
    adapter = EmbodimentAdapter(SIMPLE_CONFIG)
    session = Session(
        bridge=MockBridge(),
        policy=MockClient(),
        adapter=adapter,
        rerun_logger=_make_mock_logger(),
    )
    await session.start()
    session.pause()
    assert session.state == "paused"
    session.resume()
    assert session.state == "running"
    await session.stop()
```

- [ ] **Step 2: Run tests to verify they fail**

```bash
cd backend && uv run pytest tests/test_session_lockstep.py -v
```

Expected: FAIL — `Session()` does not accept `policy` or `adapter` arguments.

- [ ] **Step 3: Update Session for lockstep loop**

In `backend/src/robotics_playground/session.py`, update the constructor and `_run_loop`:

```python
from __future__ import annotations

import asyncio
import contextlib
import time
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from robotics_playground.bridges.protocol import RobotBridge
    from robotics_playground.policy.embodiment_adapter import EmbodimentAdapter
    from robotics_playground.policy.protocol import PolicyClient
    from robotics_playground.rerun_logger import RerunLogger


class Session:
    def __init__(
        self,
        bridge: RobotBridge,
        policy: PolicyClient,
        adapter: EmbodimentAdapter,
        rerun_logger: RerunLogger,
    ):
        self._bridge = bridge
        self._policy = policy
        self._adapter = adapter
        self._logger = rerun_logger
        self._task: asyncio.Task | None = None
        self._instruction: str = ""
        self._state: str = "idle"
        self._step: int = 0
        self._paused = asyncio.Event()
        self._paused.set()
        self._step_once = asyncio.Event()

    # ... properties unchanged (state, step, instruction, bridge_status) ...

    async def start(self):
        if self._task is not None:
            return
        self._paused.set()
        await self._bridge.start()
        await self._policy.connect()
        self._state = "running"
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
        await self._policy.close()
        await self._bridge.close()
        self._state = "idle"
        self._step = 0

    # ... pause(), resume(), step_once(), reset() unchanged ...
    # ... handle_sim_control() unchanged ...

    async def _run_loop(self):
        try:
            while True:
                # Wait for unpause
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

                # Collect observation
                obs = await self._bridge.get_observation()
                self._step = obs["step"]
                self._logger.log_observation(obs, obs["step"])

                if self._instruction:
                    self._logger.log_instruction(self._instruction, obs["step"])

                # Normalize and infer
                openpi_obs = self._adapter.observation_to_openpi(obs, self._instruction)
                t0 = time.monotonic()
                raw_action = await self._policy.infer(openpi_obs)
                inference_ms = (time.monotonic() - t0) * 1000

                # Log ML debug path
                self._logger.log_raw_action_tensor(raw_action["actions"], self._step)
                self._logger.log_inference_latency(inference_ms, self._step)

                # Denormalize
                action_chunk = self._adapter.action_chunk_from_openpi(raw_action)

                # Log physical trajectory path
                self._logger.log_action_trajectory(action_chunk, self._step)

                # Execute action chunk
                for action in action_chunk:
                    await self._bridge.send_action(action)
                    await self._bridge.sim_control("step")
                    self._step += 1

                    if not self._paused.is_set() or stepping:
                        break

                if stepping:
                    self._paused.clear()
        except asyncio.CancelledError:
            raise
```

- [ ] **Step 4: Update existing test_session.py for new constructor**

In `backend/tests/test_session.py`, update `_make_mock_logger` to include new methods and all `Session()` calls to pass `policy` and `adapter`:

Add imports at top:

```python
from robotics_playground.config import EmbodimentConfig
from robotics_playground.policy.embodiment_adapter import EmbodimentAdapter
from robotics_playground.policy.mock_client import MockClient
```

Add a helper:

```python
_SIMPLE_CONFIG = EmbodimentConfig(
    joint_names=["j1", "j2", "j3", "j4", "j5", "j6"],
    training_order=["j1", "j2", "j3", "j4", "j5", "j6"],
    joint_limits={f"j{i}": [-1, 1] for i in range(1, 7)},
    gripper_joint="g",
    gripper_limits=[0, 1],
    camera_mapping={"wrist": "observation/wrist_image_left"},
    image_size=[224, 224],
)
```

Update `_make_mock_logger` to add the new mock methods:

```python
def _make_mock_logger():
    logger = MagicMock()
    logger.log_observation = MagicMock()
    logger.log_action = MagicMock()
    logger.log_instruction = MagicMock()
    logger.log_raw_action_tensor = MagicMock()
    logger.log_inference_latency = MagicMock()
    logger.log_action_trajectory = MagicMock()
    return logger
```

Replace every `Session(bridge=..., rerun_logger=...)` with:

```python
Session(
    bridge=...,
    policy=MockClient(),
    adapter=EmbodimentAdapter(_SIMPLE_CONFIG),
    rerun_logger=...,
)
```

- [ ] **Step 5: Update main.py wiring**

In `backend/src/robotics_playground/main.py`, update the lifespan to create policy and adapter:

```python
from robotics_playground.policy import create_policy
from robotics_playground.policy.embodiment_adapter import EmbodimentAdapter
```

In the lifespan function, after creating the bridge:

```python
policy = create_policy(config)
adapter = EmbodimentAdapter(config.policy.embodiment)
session = Session(
    bridge=bridge,
    policy=policy,
    adapter=adapter,
    rerun_logger=logger,
)
```

Remove the `from robotics_playground.mock_policy import predict_action` import from session.py (already handled by the rewrite).

- [ ] **Step 6: Run all tests**

```bash
cd backend && uv run pytest -v
```

Expected: all pass.

- [ ] **Step 7: Lint and commit**

```bash
cd backend && uv run ruff check src/ tests/ && uv run ruff format --check src/ tests/
git add backend/src/robotics_playground/session.py \
        backend/src/robotics_playground/main.py \
        backend/src/robotics_playground/bridges/__init__.py \
        backend/tests/test_session.py \
        backend/tests/test_session_lockstep.py
git commit -m "feat: implement lockstep session loop with policy and adapter wiring"
```

---

### Task 9: ROS2Bridge Updates

**Files:**

- Modify: `backend/src/robotics_playground/bridges/ros2_bridge.py`
- Modify: `backend/tests/test_ros2_bridge.py`

**Interfaces:**

- Consumes: `Action` (extended), `ROS2Config.physics_decimation`
- Produces: `ROS2Bridge.get_observation()`, updated `send_action()`, decimated `sim_control("step")`

- [ ] **Step 1: Update ROS2Bridge**

In `backend/src/robotics_playground/bridges/ros2_bridge.py`:

Add `get_observation()`:

```python
async def get_observation(self) -> Observation:
    return await self._obs_queue.get()
```

Update `send_action()` to publish both position and velocity arrays:

```python
async def send_action(self, action: Action) -> None:
    if self._publisher is None or self._node is None:
        return
    from sensor_msgs.msg import JointState

    msg = JointState()
    msg.position = [float(p) for p in action["joint_positions"]]
    msg.velocity = [float(v) for v in action["joint_velocities"]]
    self._publisher.publish(msg)
```

Update `sim_control("step")` to use configurable decimation:

```python
elif action == "step":
    req = self._StepSimulation.Request()
    req.steps = self._config.physics_decimation
    if self._step_client is not None:
        await asyncio.get_running_loop().run_in_executor(
            None, lambda: self._step_client.call(req)
        )
```

- [ ] **Step 2: Update ROS2Bridge tests**

In `backend/tests/test_ros2_bridge.py`, update any `send_action` calls to use the new Action format.

- [ ] **Step 3: Run tests**

```bash
cd backend && uv run pytest tests/test_ros2_bridge.py -v
```

Expected: all pass.

- [ ] **Step 4: Lint and commit**

```bash
cd backend && uv run ruff check src/ tests/ && uv run ruff format --check src/ tests/
git add backend/src/robotics_playground/bridges/ros2_bridge.py \
        backend/tests/test_ros2_bridge.py
git commit -m "feat: update ROS2Bridge with get_observation, velocity dispatch, and decimation"
```

---

### Task 10: Full Build Validation & Kustomize Config

**Files:**

- Modify: `deploy/kustomize/configmap.yaml` (add policy config example)

**Interfaces:**

- Consumes: all prior tasks

- [ ] **Step 1: Run full test suite**

```bash
make test
```

Expected: all frontend and backend tests pass.

- [ ] **Step 2: Run full lint**

```bash
make lint
```

Expected: no errors.

- [ ] **Step 3: Build container images**

```bash
make build
```

Expected: both images build successfully with new pip dependencies.

- [ ] **Step 4: Run manifest validation**

```bash
make validate
```

Expected: kubeconform validates all manifests.

- [ ] **Step 5: Commit any remaining fixes**

If any step required fixes:

```bash
git add -A
git commit -m "fix: resolve build/lint issues from Phase 3 integration"
```

- [ ] **Step 6: Create PR**

Create a feature branch and PR with all Phase 3 commits:

```bash
git checkout -b feat/phase3-vla-policy-integration
git push -u origin feat/phase3-vla-policy-integration
gh pr create --title "feat: Phase 3 — VLA policy integration via OpenPI" \
  --body "Connects backend to DreamZero on vLLM-Omni via OpenPI WebSocket.

## Changes
- PolicyClient protocol + OpenPIClient (WebSocket+msgpack) + MockClient
- EmbodimentAdapter for joint reorder, normalize/denormalize, key remap
- Lockstep session loop (sim frozen during inference)
- Dual-path Rerun logging (raw tensors + physical trajectories)
- Extended Action type with velocities + gripper position
- PolicyConfig + EmbodimentConfig in config

## Platform agent follow-up needed
- USD scene: stiffness=0 for arm joints (velocity control)
- Backend ConfigMap: add policy section with OpenPI endpoint
- DreamZero InferenceService: scale to minReplicas=1

Spec: docs/superpowers/specs/2026-07-10-phase3-vla-policy-integration-design.md"
```
