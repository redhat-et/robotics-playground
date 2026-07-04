# Robotics Playground — Phase 1: Skeleton — UI Shell + Mock Backend

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Deliver end-to-end data flow with mock data — a user opens the playground, sees a mock camera feed and joint plots in the Rerun viewer, types an instruction, and sees status updates. No GPU, no real robot, no real policy server required.

**Architecture:** React/PatternFly frontend communicates with a Python/FastAPI backend over WebSocket. The backend runs a mock observation-action loop (synthetic images + sinusoidal joints → random actions) and logs everything to a Rerun entity tree. The browser embeds the Rerun web viewer via iframe to display camera feeds, joint plots, and action telemetry. A Hummingbird compatibility spike validates that Rerun SDK works in distroless containers.

**Tech Stack:**

- Frontend: React 18, PatternFly 6, TypeScript 5, Webpack 5 (Module Federation), Vitest, Testing Library
- Backend: Python 3.14, FastAPI, Uvicorn, Rerun SDK 0.33, NumPy, Pytest, pytest-anyio
- Containers: `hi/nginx:latest` (frontend), `hi/python:3.14` (backend)

## Global Constraints

- Apache 2.0 license
- Conventional Commits for commit messages
- YAML: 2-space indent
- Tests first: write tests before implementation
- Always run `make lint`, `make test`, `make build` before committing
- Follow RHOAI/OpenShift AI design language — no custom themes; use PatternFly variables only
- Frontend exposes `/remoteEntry.js` for RHOAI plugin integration AND works as standalone SPA
- No hardcoded namespaces in K8s manifests

## Existing State (from Phase 0 + partial Phase 1 work)

The following are already implemented and committed to `main`:

- **Frontend layout**: `App.tsx` (masthead + page), `RoboticsPlayground.tsx` (grid layout: sidebar + main area), `RoboticsPlayground.css`
- **Frontend components**: `ChatPanel.tsx`, `SimulationControlPanel.tsx`, `PolicyBar.tsx`, `VisualizationPanel.tsx`
- **Frontend hook**: `useSession.ts` (WebSocket connection, instruction send, sim control)
- **Backend mock bridges**: `mock_robot.py` (10 Hz synthetic observations), `mock_policy.py` (random actions, 50ms latency)
- **Backend session**: `session.py` (state machine, observation-action loop)
- **Backend Rerun logger**: `rerun_logger.py` (logs observations, actions, instructions)
- **Backend WebSocket**: `/ws/sessions/{id}` in `main.py` (status broadcast, instruction/sim_control handling)
- **Backend tests**: `test_health.py`, `test_mock_policy.py`, `test_mock_robot.py`, `test_session.py`, `test_websocket.py`
- **Frontend tests**: `App.test.tsx` (smoke tests for ChatPanel, SimulationControlPanel)

## Known Issues in Existing Code

1. **Makefile uses bare `pytest` / `ruff`** — not activated from `.venv`, so `make test` and `make lint` fail on backend
2. **`pytest-anyio` not in dependencies** — async tests marked `@pytest.mark.anyio` get `PytestUnknownMarkWarning` and don't execute as async
3. **Rerun viewer URL hardcoded to v0.22.1** in `VisualizationPanel.tsx` — backend uses Rerun SDK 0.33; viewer must match
4. **`@testing-library/user-event` not installed** — needed for interaction tests (typing, clicking)
5. **Frontend test coverage minimal** — no tests for `PolicyBar`, `VisualizationPanel`, `useSession` hook, or user interactions

## File Map

```text
frontend/
├── src/
│   ├── components/
│   │   ├── ChatPanel.tsx            # Existing (tested in Task 4)
│   │   ├── PolicyBar.tsx            # Existing (tested in Task 4)
│   │   ├── SimulationControlPanel.tsx # Existing (tested in Task 4)
│   │   └── VisualizationPanel.tsx   # Modify: fix Rerun viewer URL (Task 2)
│   ├── hooks/
│   │   └── useSession.ts            # Existing (tested in Task 5)
│   ├── App.tsx                      # Existing
│   ├── RoboticsPlayground.tsx       # Existing
│   └── RoboticsPlayground.css       # Existing
├── test/
│   ├── setup.ts                     # Existing
│   ├── App.test.tsx                 # Modify: narrow to app-level smoke test (Task 4)
│   ├── ChatPanel.test.tsx           # Create: unit + interaction tests (Task 4)
│   ├── SimulationControlPanel.test.tsx # Create: unit + interaction tests (Task 4)
│   ├── PolicyBar.test.tsx           # Create: unit tests with fetch mock (Task 4)
│   ├── VisualizationPanel.test.tsx  # Create: unit tests (Task 4)
│   └── useSession.test.ts          # Create: hook tests with WebSocket mock (Task 5)
├── package.json                     # Modify: add @testing-library/user-event (Task 4)
└── vitest.config.ts                 # Existing

backend/
├── src/robotics_playground/
│   ├── main.py                      # Existing
│   ├── config.py                    # Existing
│   ├── session.py                   # Existing
│   ├── mock_robot.py                # Existing
│   ├── mock_policy.py               # Existing
│   └── rerun_logger.py             # Existing
├── tests/
│   ├── conftest.py                  # Create: shared fixtures (Task 3)
│   ├── test_health.py               # Existing
│   ├── test_mock_policy.py          # Existing (fixed by Task 1)
│   ├── test_mock_robot.py           # Existing (fixed by Task 1)
│   ├── test_session.py              # Modify: expand coverage (Task 3)
│   ├── test_websocket.py            # Modify: expand coverage (Task 3)
│   └── test_rerun_logger.py         # Create: unit tests (Task 3)
├── pyproject.toml                   # Modify: add pytest-anyio dep (Task 1)
└── Containerfile                    # Existing (used in Task 7 spike)

Makefile                             # Modify: fix venv activation (Task 1)

docs/spikes/
└── 2026-07-03-hummingbird-rerun-compatibility.md  # Create (Task 7)
```

---

### Task 1: Fix Backend Tooling — Makefile + Dependencies

**Files:**

- Modify: `Makefile` (backend targets use `uv run`)
- Modify: `backend/pyproject.toml` (add `pytest-anyio` to dev deps)

**Interfaces:**

- Produces: `make test` and `make lint` pass cleanly. Async tests execute correctly via `pytest-anyio`.

- [ ] **Step 1: Add `pytest-anyio` to backend dev dependencies**

`backend/pyproject.toml` — add `pytest-anyio` to `[project.optional-dependencies] dev`:

```toml
[project.optional-dependencies]
dev = [
    "pytest>=8.3.0",
    "pytest-anyio>=0.0.0",
    "httpx>=0.28.0",
    "ruff>=0.9.0",
    "anyio>=4.0.0",
]
```

- [ ] **Step 2: Install updated dependencies**

```bash
cd backend && uv sync --extra dev
```

Expected: installs `pytest-anyio` into `.venv`.

- [ ] **Step 3: Fix Makefile backend targets to use `uv run`**

Replace the backend targets in `Makefile`:

```makefile
## Start backend dev server
dev-backend:
 cd backend && uv run uvicorn robotics_playground.main:app --reload --host 0.0.0.0 --port 8000

## Run backend tests
test-backend:
 cd backend && uv run pytest -v

## Lint backend code
lint-backend:
 cd backend && uv run ruff check src/ tests/ && uv run ruff format --check src/ tests/
```

- [ ] **Step 4: Verify lint passes**

```bash
make lint-backend
```

Expected: `ruff check` and `ruff format --check` both pass with no errors.

- [ ] **Step 5: Verify tests pass (with async tests actually running)**

```bash
make test-backend
```

Expected: all tests pass. The `pytest-anyio` marker warnings should be gone. Async test functions should run as actual coroutines.

- [ ] **Step 6: Verify full lint + test suite**

```bash
make lint
make test
```

Expected: both pass (frontend + backend).

- [ ] **Step 7: Commit**

```bash
git add Makefile backend/pyproject.toml backend/uv.lock
git commit -m "fix: use uv run in Makefile and add pytest-anyio dependency

Backend Make targets now run tools through uv, ensuring the .venv is
used. Added pytest-anyio so async test functions execute correctly.

Assisted-By: Claude <noreply@anthropic.com>"
```

---

### Task 2: Fix Rerun Viewer Version in Frontend

**Files:**

- Modify: `frontend/src/components/VisualizationPanel.tsx`

**Interfaces:**

- Consumes: Rerun gRPC stream served by backend `RerunLogger` on port 9876
- Produces: Rerun web viewer iframe loads the correct version (matching SDK 0.33) and connects to the backend stream

- [ ] **Step 1: Update the Rerun viewer URL**

In `frontend/src/components/VisualizationPanel.tsx`, change the `RERUN_VIEWER_URL` constant from:

```typescript
const RERUN_VIEWER_URL = 'https://app.rerun.io/version/0.22.1/';
```

to:

```typescript
const RERUN_VIEWER_URL = 'https://app.rerun.io/version/0.33.1/';
```

- [ ] **Step 2: Verify frontend still builds**

```bash
cd frontend && npm run build
```

Expected: build succeeds, `dist/` output includes `index.html` and `remoteEntry.js`.

- [ ] **Step 3: Verify lint + typecheck**

```bash
cd frontend && npm run lint && npm run typecheck
```

Expected: no errors.

- [ ] **Step 4: Commit**

```bash
git add frontend/src/components/VisualizationPanel.tsx
git commit -m "fix: update Rerun viewer URL to match SDK v0.33

The backend uses Rerun SDK 0.33 but the viewer iframe was loading
v0.22.1, causing connection failures.

Assisted-By: Claude <noreply@anthropic.com>"
```

---

### Task 3: Backend Test Coverage — RerunLogger + Session + WebSocket

**Files:**

- Create: `backend/tests/conftest.py`
- Create: `backend/tests/test_rerun_logger.py`
- Modify: `backend/tests/test_session.py` (expand coverage)
- Modify: `backend/tests/test_websocket.py` (expand coverage)

**Interfaces:**

- Consumes: `RerunLogger` class from `rerun_logger.py`, `Session` class from `session.py`, FastAPI `app` from `main.py`
- Produces: comprehensive backend test suite covering RerunLogger methods, Session observation loop integration, and WebSocket protocol edge cases

- [ ] **Step 1: Create shared test fixtures**

`backend/tests/conftest.py`:

```python
from __future__ import annotations

from unittest.mock import MagicMock

import pytest

from robotics_playground.session import Session


@pytest.fixture
def mock_rerun():
    return MagicMock()


@pytest.fixture
def mock_logger():
    logger = MagicMock()
    logger.log_observation = MagicMock()
    logger.log_action = MagicMock()
    logger.log_instruction = MagicMock()
    return logger


@pytest.fixture
def session(mock_logger):
    return Session(rerun_logger=mock_logger)
```

- [ ] **Step 2: Write RerunLogger unit tests**

`backend/tests/test_rerun_logger.py`:

```python
from __future__ import annotations

from unittest.mock import MagicMock, patch

import numpy as np

from robotics_playground.rerun_logger import RerunLogger


@patch("robotics_playground.rerun_logger.rr")
def test_start_initializes_rerun(mock_rr: MagicMock):
    logger = RerunLogger(port=9876)
    logger.start()
    mock_rr.init.assert_called_once_with("robotics_playground")
    mock_rr.serve_grpc.assert_called_once_with(grpc_port=9876)


@patch("robotics_playground.rerun_logger.rr")
def test_start_is_idempotent(mock_rr: MagicMock):
    logger = RerunLogger(port=9876)
    logger.start()
    logger.start()
    assert mock_rr.init.call_count == 1


@patch("robotics_playground.rerun_logger.rr")
def test_log_observation_logs_image_and_joints(mock_rr: MagicMock):
    logger = RerunLogger(port=9876, policy_index=0)
    logger.start()
    image = np.zeros((240, 320, 3), dtype=np.uint8)
    joints = [0.1, 0.2, 0.3, 0.4, 0.5, 0.6]

    logger.log_observation(image, joints, step=5)

    mock_rr.set_time.assert_called_with("step", sequence=5)
    mock_rr.log.assert_any_call("session/policy_0/camera/wrist", mock_rr.Image.return_value)
    assert mock_rr.log.call_count == 7  # 1 image + 6 joints


@patch("robotics_playground.rerun_logger.rr")
def test_log_action_logs_all_dimensions(mock_rr: MagicMock):
    logger = RerunLogger(port=9876, policy_index=0)
    logger.start()
    action = np.array([0.1, -0.2, 0.3, -0.4, 0.5, -0.6], dtype=np.float32)

    logger.log_action(action, step=10)

    mock_rr.set_time.assert_called_with("step", sequence=10)
    assert mock_rr.log.call_count == 6


@patch("robotics_playground.rerun_logger.rr")
def test_log_instruction_logs_text(mock_rr: MagicMock):
    logger = RerunLogger(port=9876)
    logger.start()

    logger.log_instruction("pick up block", step=3)

    mock_rr.set_time.assert_called_with("step", sequence=3)
    mock_rr.log.assert_called_once_with("session/instructions", mock_rr.TextLog.return_value)


@patch("robotics_playground.rerun_logger.rr")
def test_policy_index_changes_entity_prefix(mock_rr: MagicMock):
    logger = RerunLogger(port=9876, policy_index=1)
    logger.start()
    image = np.zeros((240, 320, 3), dtype=np.uint8)

    logger.log_observation(image, [0.0] * 6, step=0)

    logged_paths = [call.args[0] for call in mock_rr.log.call_args_list]
    assert all("policy_1" in p for p in logged_paths)
```

- [ ] **Step 3: Run RerunLogger tests**

```bash
cd backend && uv run pytest tests/test_rerun_logger.py -v
```

Expected: all 6 tests pass.

- [ ] **Step 4: Expand Session tests with observation loop and edge case coverage**

Replace `backend/tests/test_session.py`:

```python
from __future__ import annotations

import asyncio

import pytest

from robotics_playground.session import Session


def _make_mock_logger():
    from unittest.mock import MagicMock

    logger = MagicMock()
    logger.log_observation = MagicMock()
    logger.log_action = MagicMock()
    logger.log_instruction = MagicMock()
    return logger


def test_session_initial_state():
    session = Session(rerun_logger=_make_mock_logger())
    assert session.state == "idle"
    assert session.step == 0
    assert session.instruction == ""


def test_send_instruction_stores_text():
    session = Session(rerun_logger=_make_mock_logger())
    session.send_instruction("wave")
    assert session.instruction == "wave"


def test_send_instruction_overwrites_previous():
    session = Session(rerun_logger=_make_mock_logger())
    session.send_instruction("wave")
    session.send_instruction("pick up block")
    assert session.instruction == "pick up block"


@pytest.mark.anyio
async def test_start_stop_lifecycle():
    session = Session(rerun_logger=_make_mock_logger())
    assert session.state == "idle"

    await session.start()
    assert session.state == "running"

    await session.stop()
    assert session.state == "idle"


@pytest.mark.anyio
async def test_start_is_idempotent():
    session = Session(rerun_logger=_make_mock_logger())
    await session.start()
    await session.start()
    assert session.state == "running"
    await session.stop()


@pytest.mark.anyio
async def test_stop_from_idle_is_noop():
    session = Session(rerun_logger=_make_mock_logger())
    await session.stop()
    assert session.state == "idle"


@pytest.mark.anyio
async def test_pause_resume():
    session = Session(rerun_logger=_make_mock_logger())
    await session.start()
    assert session.state == "running"

    session.pause()
    assert session.state == "paused"

    session.resume()
    assert session.state == "running"

    await session.stop()


@pytest.mark.anyio
async def test_pause_from_idle_is_noop():
    session = Session(rerun_logger=_make_mock_logger())
    session.pause()
    assert session.state == "idle"


@pytest.mark.anyio
async def test_resume_from_idle_is_noop():
    session = Session(rerun_logger=_make_mock_logger())
    session.resume()
    assert session.state == "idle"


@pytest.mark.anyio
async def test_reset_clears_state():
    session = Session(rerun_logger=_make_mock_logger())
    await session.start()
    session.send_instruction("pick up block")

    await session.reset()
    assert session.state == "idle"
    assert session.instruction == ""
    assert session.step == 0


@pytest.mark.anyio
async def test_handle_sim_control_play_from_idle():
    session = Session(rerun_logger=_make_mock_logger())
    await session.handle_sim_control("play")
    assert session.state == "running"
    await session.stop()


@pytest.mark.anyio
async def test_handle_sim_control_pause_and_resume():
    session = Session(rerun_logger=_make_mock_logger())
    await session.handle_sim_control("play")
    await session.handle_sim_control("pause")
    assert session.state == "paused"
    await session.handle_sim_control("play")
    assert session.state == "running"
    await session.stop()


@pytest.mark.anyio
async def test_handle_sim_control_stop():
    session = Session(rerun_logger=_make_mock_logger())
    await session.handle_sim_control("play")
    await session.handle_sim_control("stop")
    assert session.state == "idle"


@pytest.mark.anyio
async def test_handle_sim_control_reset():
    session = Session(rerun_logger=_make_mock_logger())
    await session.handle_sim_control("play")
    session.send_instruction("wave")
    await session.handle_sim_control("reset")
    assert session.state == "idle"
    assert session.instruction == ""


@pytest.mark.anyio
async def test_handle_sim_control_step_from_idle():
    session = Session(rerun_logger=_make_mock_logger())
    await session.handle_sim_control("step")
    assert session.state == "paused"
    await session.stop()


@pytest.mark.anyio
async def test_handle_sim_control_unknown_action_is_noop():
    session = Session(rerun_logger=_make_mock_logger())
    await session.handle_sim_control("unknown_action")
    assert session.state == "idle"


@pytest.mark.anyio
async def test_observation_loop_logs_data():
    mock_logger = _make_mock_logger()
    session = Session(rerun_logger=mock_logger)
    await session.start()

    await asyncio.sleep(0.35)

    await session.stop()

    assert mock_logger.log_observation.call_count >= 2
    assert mock_logger.log_action.call_count >= 2


@pytest.mark.anyio
async def test_observation_loop_logs_instruction_when_set():
    mock_logger = _make_mock_logger()
    session = Session(rerun_logger=mock_logger)
    session.send_instruction("wave")
    await session.start()

    await asyncio.sleep(0.25)

    await session.stop()

    assert mock_logger.log_instruction.call_count >= 1
```

- [ ] **Step 5: Run updated Session tests**

```bash
cd backend && uv run pytest tests/test_session.py -v
```

Expected: all tests pass (~19 tests).

- [ ] **Step 6: Expand WebSocket test coverage**

Replace `backend/tests/test_websocket.py`:

```python
from __future__ import annotations

from unittest.mock import MagicMock, patch

from fastapi.testclient import TestClient

from robotics_playground.main import app


@patch("robotics_playground.rerun_logger.rr")
def test_websocket_connect_receives_status(mock_rr: MagicMock):
    with TestClient(app) as client, client.websocket_connect("/ws/sessions/test") as ws:
        data = ws.receive_json()
        assert data["type"] == "status"
        assert "state" in data
        assert "step" in data
        assert "instruction" in data


@patch("robotics_playground.rerun_logger.rr")
def test_websocket_connect_and_close(mock_rr: MagicMock):
    with TestClient(app) as client, client.websocket_connect("/ws/sessions/test"):
        pass


@patch("robotics_playground.rerun_logger.rr")
def test_websocket_instruction_flow(mock_rr: MagicMock):
    with TestClient(app) as client, client.websocket_connect("/ws/sessions/test") as ws:
        ws.send_json({"type": "instruction", "text": "wave"})
        for _ in range(10):
            data = ws.receive_json()
            if data["type"] == "instruction_ack":
                break
        assert data["type"] == "instruction_ack"
        assert data["status"] == "received"
        assert data["text"] == "wave"


@patch("robotics_playground.rerun_logger.rr")
def test_websocket_instruction_ack_includes_text(mock_rr: MagicMock):
    with TestClient(app) as client, client.websocket_connect("/ws/sessions/test") as ws:
        ws.send_json({"type": "instruction", "text": "pick up the red block"})
        for _ in range(10):
            data = ws.receive_json()
            if data["type"] == "instruction_ack":
                break
        assert data["text"] == "pick up the red block"


@patch("robotics_playground.rerun_logger.rr")
def test_websocket_sim_control_play(mock_rr: MagicMock):
    with TestClient(app) as client, client.websocket_connect("/ws/sessions/test") as ws:
        ws.send_json({"type": "sim_control", "action": "play"})
        data = ws.receive_json()
        assert data["type"] == "status"


@patch("robotics_playground.rerun_logger.rr")
def test_websocket_malformed_json_ignored(mock_rr: MagicMock):
    with TestClient(app) as client, client.websocket_connect("/ws/sessions/test") as ws:
        ws.send_text("not valid json")
        data = ws.receive_json()
        assert data["type"] == "status"


@patch("robotics_playground.rerun_logger.rr")
def test_websocket_unknown_message_type_ignored(mock_rr: MagicMock):
    with TestClient(app) as client, client.websocket_connect("/ws/sessions/test") as ws:
        ws.send_json({"type": "unknown_type", "data": 123})
        data = ws.receive_json()
        assert data["type"] == "status"


@patch("robotics_playground.rerun_logger.rr")
def test_websocket_multiple_instructions(mock_rr: MagicMock):
    with TestClient(app) as client, client.websocket_connect("/ws/sessions/test") as ws:
        ws.send_json({"type": "instruction", "text": "first"})
        acks = []
        for _ in range(20):
            data = ws.receive_json()
            if data["type"] == "instruction_ack":
                acks.append(data)
                break

        ws.send_json({"type": "instruction", "text": "second"})
        for _ in range(20):
            data = ws.receive_json()
            if data["type"] == "instruction_ack":
                acks.append(data)
                break

        assert len(acks) == 2
        assert acks[0]["text"] == "first"
        assert acks[1]["text"] == "second"
```

- [ ] **Step 7: Run WebSocket tests**

```bash
cd backend && uv run pytest tests/test_websocket.py -v
```

Expected: all 8 tests pass.

- [ ] **Step 8: Run full backend test suite**

```bash
make test-backend
```

Expected: all tests pass (~37 total: health 2 + mock_policy 2 + mock_robot 2 + session 19 + websocket 8 + rerun_logger 6).

- [ ] **Step 9: Commit**

```bash
git add backend/tests/
git commit -m "test(backend): add RerunLogger tests and expand Session/WebSocket coverage

New test_rerun_logger.py covers init, idempotency, observation/action/
instruction logging, and policy index namespacing. Session tests now
cover the observation loop, edge cases (double start, stop from idle,
unknown sim_control). WebSocket tests cover malformed JSON, unknown
message types, and multi-instruction flows.

Assisted-By: Claude <noreply@anthropic.com>"
```

---

### Task 4: Frontend Test Coverage — Component Unit Tests

**Files:**

- Modify: `frontend/package.json` (add `@testing-library/user-event`)
- Create: `frontend/test/ChatPanel.test.tsx`
- Create: `frontend/test/SimulationControlPanel.test.tsx`
- Create: `frontend/test/PolicyBar.test.tsx`
- Create: `frontend/test/VisualizationPanel.test.tsx`
- Modify: `frontend/test/App.test.tsx` (narrow to app-level smoke test)

**Interfaces:**

- Consumes: all frontend components from `src/components/`, `useSession` hook types from `src/hooks/useSession.ts`
- Produces: component-level unit tests with interaction testing (user-event), fetch mocking for PolicyBar, conditional rendering tests for VisualizationPanel

- [ ] **Step 1: Add `@testing-library/user-event` dependency**

```bash
cd frontend && npm install --save-dev @testing-library/user-event
```

- [ ] **Step 2: Create ChatPanel interaction tests**

`frontend/test/ChatPanel.test.tsx`:

```tsx
import { describe, it, expect, vi } from 'vitest';
import { render, screen } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import ChatPanel from '../src/components/ChatPanel';

describe('ChatPanel', () => {
  it('renders the instructions heading', () => {
    render(<ChatPanel messages={[]} onSendInstruction={vi.fn()} connected={false} />);
    expect(screen.getByText('Instructions')).toBeInTheDocument();
  });

  it('disables input when not connected', () => {
    render(<ChatPanel messages={[]} onSendInstruction={vi.fn()} connected={false} />);
    const input = screen.getByPlaceholderText('Tell the robot what to do...');
    expect(input).toBeDisabled();
  });

  it('enables input when connected', () => {
    render(<ChatPanel messages={[]} onSendInstruction={vi.fn()} connected={true} />);
    const input = screen.getByPlaceholderText('Tell the robot what to do...');
    expect(input).not.toBeDisabled();
  });

  it('disables send button when input is empty', () => {
    render(<ChatPanel messages={[]} onSendInstruction={vi.fn()} connected={true} />);
    const button = screen.getByRole('button', { name: 'Send' });
    expect(button).toBeDisabled();
  });

  it('calls onSendInstruction when send button is clicked', async () => {
    const onSend = vi.fn();
    const user = userEvent.setup();
    render(<ChatPanel messages={[]} onSendInstruction={onSend} connected={true} />);

    const input = screen.getByPlaceholderText('Tell the robot what to do...');
    await user.type(input, 'pick up block');
    await user.click(screen.getByRole('button', { name: 'Send' }));

    expect(onSend).toHaveBeenCalledWith('pick up block');
  });

  it('clears input after sending', async () => {
    const user = userEvent.setup();
    render(<ChatPanel messages={[]} onSendInstruction={vi.fn()} connected={true} />);

    const input = screen.getByPlaceholderText('Tell the robot what to do...');
    await user.type(input, 'wave');
    await user.click(screen.getByRole('button', { name: 'Send' }));

    expect(input).toHaveValue('');
  });

  it('sends on Enter key', async () => {
    const onSend = vi.fn();
    const user = userEvent.setup();
    render(<ChatPanel messages={[]} onSendInstruction={onSend} connected={true} />);

    const input = screen.getByPlaceholderText('Tell the robot what to do...');
    await user.type(input, 'wave{Enter}');

    expect(onSend).toHaveBeenCalledWith('wave');
  });

  it('does not send whitespace-only input', async () => {
    const onSend = vi.fn();
    const user = userEvent.setup();
    render(<ChatPanel messages={[]} onSendInstruction={onSend} connected={true} />);

    const input = screen.getByPlaceholderText('Tell the robot what to do...');
    await user.type(input, '   {Enter}');

    expect(onSend).not.toHaveBeenCalled();
  });

  it('renders user and system messages', () => {
    const messages = [
      { id: '1', role: 'user' as const, text: 'Pick up block', timestamp: 1 },
      { id: '2', role: 'system' as const, text: 'received: Pick up block', timestamp: 2 },
    ];
    render(<ChatPanel messages={messages} onSendInstruction={vi.fn()} connected={true} />);
    expect(screen.getByText('Pick up block')).toBeInTheDocument();
    expect(screen.getByText('received: Pick up block')).toBeInTheDocument();
  });

  it('applies correct CSS class for user messages', () => {
    const messages = [
      { id: '1', role: 'user' as const, text: 'test message', timestamp: 1 },
    ];
    render(<ChatPanel messages={messages} onSendInstruction={vi.fn()} connected={true} />);
    const messageEl = screen.getByText('test message').closest('.chat-panel__message');
    expect(messageEl).toHaveClass('chat-panel__message--user');
  });

  it('applies correct CSS class for system messages', () => {
    const messages = [
      { id: '1', role: 'system' as const, text: 'system msg', timestamp: 1 },
    ];
    render(<ChatPanel messages={messages} onSendInstruction={vi.fn()} connected={true} />);
    const messageEl = screen.getByText('system msg').closest('.chat-panel__message');
    expect(messageEl).toHaveClass('chat-panel__message--system');
  });
});
```

- [ ] **Step 3: Run ChatPanel tests**

```bash
cd frontend && npm test -- --reporter=verbose 2>&1 | grep -E "✓|✗|FAIL|PASS|ChatPanel"
```

Expected: all ChatPanel tests pass.

- [ ] **Step 4: Create SimulationControlPanel tests**

`frontend/test/SimulationControlPanel.test.tsx`:

```tsx
import { describe, it, expect, vi } from 'vitest';
import { render, screen } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import SimulationControlPanel from '../src/components/SimulationControlPanel';

describe('SimulationControlPanel', () => {
  it('shows Idle label and Play button when idle', () => {
    render(<SimulationControlPanel state="idle" onSimControl={vi.fn()} />);
    expect(screen.getByText('Idle')).toBeInTheDocument();
    expect(screen.getByText('Play')).toBeInTheDocument();
  });

  it('shows Running label and Pause button when running', () => {
    render(<SimulationControlPanel state="running" onSimControl={vi.fn()} />);
    expect(screen.getByText('Running')).toBeInTheDocument();
    expect(screen.getByText('Pause')).toBeInTheDocument();
  });

  it('shows Paused label when paused', () => {
    render(<SimulationControlPanel state="paused" onSimControl={vi.fn()} />);
    expect(screen.getByText('Paused')).toBeInTheDocument();
  });

  it('calls onSimControl with play when Play is clicked', async () => {
    const onControl = vi.fn();
    const user = userEvent.setup();
    render(<SimulationControlPanel state="idle" onSimControl={onControl} />);

    await user.click(screen.getByText('Play'));
    expect(onControl).toHaveBeenCalledWith('play');
  });

  it('calls onSimControl with pause when Pause is clicked', async () => {
    const onControl = vi.fn();
    const user = userEvent.setup();
    render(<SimulationControlPanel state="running" onSimControl={onControl} />);

    await user.click(screen.getByText('Pause'));
    expect(onControl).toHaveBeenCalledWith('pause');
  });

  it('calls onSimControl with stop when Stop is clicked', async () => {
    const onControl = vi.fn();
    const user = userEvent.setup();
    render(<SimulationControlPanel state="running" onSimControl={onControl} />);

    await user.click(screen.getByText('Stop'));
    expect(onControl).toHaveBeenCalledWith('stop');
  });

  it('disables Stop button when idle', () => {
    render(<SimulationControlPanel state="idle" onSimControl={vi.fn()} />);
    expect(screen.getByText('Stop')).toBeDisabled();
  });

  it('disables Step button when running', () => {
    render(<SimulationControlPanel state="running" onSimControl={vi.fn()} />);
    expect(screen.getByText('Step')).toBeDisabled();
  });

  it('enables Step button when paused', async () => {
    const onControl = vi.fn();
    const user = userEvent.setup();
    render(<SimulationControlPanel state="paused" onSimControl={onControl} />);

    const stepBtn = screen.getByText('Step');
    expect(stepBtn).not.toBeDisabled();
    await user.click(stepBtn);
    expect(onControl).toHaveBeenCalledWith('step');
  });

  it('calls onSimControl with reset when Reset is clicked', async () => {
    const onControl = vi.fn();
    const user = userEvent.setup();
    render(<SimulationControlPanel state="running" onSimControl={onControl} />);

    await user.click(screen.getByText('Reset'));
    expect(onControl).toHaveBeenCalledWith('reset');
  });

  it('shows Error label for error state', () => {
    render(<SimulationControlPanel state="error" onSimControl={vi.fn()} />);
    expect(screen.getByText('Error')).toBeInTheDocument();
  });

  it('falls back to Idle label for unknown state', () => {
    render(<SimulationControlPanel state="bogus" onSimControl={vi.fn()} />);
    expect(screen.getByText('Idle')).toBeInTheDocument();
  });
});
```

- [ ] **Step 5: Run SimulationControlPanel tests**

```bash
cd frontend && npm test -- --reporter=verbose 2>&1 | grep -E "✓|✗|FAIL|PASS|SimulationControl"
```

Expected: all SimulationControlPanel tests pass.

- [ ] **Step 6: Create PolicyBar tests with fetch mock**

`frontend/test/PolicyBar.test.tsx`:

```tsx
import { describe, it, expect, vi, beforeEach } from 'vitest';
import { render, screen, waitFor } from '@testing-library/react';
import PolicyBar from '../src/components/PolicyBar';

const MOCK_MODELS = {
  models: [
    { id: 'dreamzero-v1', name: 'DreamZero', type: 'robotics' },
    { id: 'model-b', name: 'Model B', type: 'robotics' },
  ],
};

describe('PolicyBar', () => {
  beforeEach(() => {
    vi.restoreAllMocks();
  });

  it('shows loading spinner initially', () => {
    vi.spyOn(global, 'fetch').mockReturnValue(new Promise(() => {}));
    render(<PolicyBar />);
    expect(screen.getByLabelText('Loading models')).toBeInTheDocument();
  });

  it('renders model options after fetch', async () => {
    vi.spyOn(global, 'fetch').mockResolvedValue({
      json: () => Promise.resolve(MOCK_MODELS),
    } as Response);

    render(<PolicyBar />);

    await waitFor(() => {
      expect(screen.getByText('DreamZero')).toBeInTheDocument();
    });
    expect(screen.getByText('Model B')).toBeInTheDocument();
  });

  it('selects first model by default', async () => {
    vi.spyOn(global, 'fetch').mockResolvedValue({
      json: () => Promise.resolve(MOCK_MODELS),
    } as Response);

    render(<PolicyBar />);

    await waitFor(() => {
      const select = screen.getByLabelText('Select policy') as HTMLSelectElement;
      expect(select.value).toBe('dreamzero-v1');
    });
  });

  it('shows disabled select when no models available', async () => {
    vi.spyOn(global, 'fetch').mockResolvedValue({
      json: () => Promise.resolve({ models: [] }),
    } as Response);

    render(<PolicyBar />);

    await waitFor(() => {
      expect(screen.getByText('No models available')).toBeInTheDocument();
    });
  });

  it('handles fetch error gracefully', async () => {
    vi.spyOn(global, 'fetch').mockRejectedValue(new Error('Network error'));

    render(<PolicyBar />);

    await waitFor(() => {
      expect(screen.getByText('No models available')).toBeInTheDocument();
    });
  });

  it('renders the Split button', async () => {
    vi.spyOn(global, 'fetch').mockResolvedValue({
      json: () => Promise.resolve(MOCK_MODELS),
    } as Response);

    render(<PolicyBar />);
    expect(screen.getByText('Split')).toBeInTheDocument();
  });

  it('fetches from correct API endpoint', async () => {
    const fetchSpy = vi.spyOn(global, 'fetch').mockResolvedValue({
      json: () => Promise.resolve(MOCK_MODELS),
    } as Response);

    render(<PolicyBar />);

    await waitFor(() => {
      expect(fetchSpy).toHaveBeenCalledWith('/api/models?type=robotics');
    });
  });
});
```

- [ ] **Step 7: Run PolicyBar tests**

```bash
cd frontend && npm test -- --reporter=verbose 2>&1 | grep -E "✓|✗|FAIL|PASS|PolicyBar"
```

Expected: all PolicyBar tests pass.

- [ ] **Step 8: Create VisualizationPanel tests**

`frontend/test/VisualizationPanel.test.tsx`:

```tsx
import { describe, it, expect } from 'vitest';
import { render, screen } from '@testing-library/react';
import VisualizationPanel from '../src/components/VisualizationPanel';

describe('VisualizationPanel', () => {
  it('shows empty state when not connected', () => {
    render(<VisualizationPanel connected={false} />);
    expect(screen.getByText('Connecting to backend...')).toBeInTheDocument();
  });

  it('renders Rerun iframe when connected', () => {
    render(<VisualizationPanel connected={true} />);
    const iframe = document.querySelector('iframe');
    expect(iframe).not.toBeNull();
    expect(iframe?.title).toBe('Rerun Viewer');
  });

  it('iframe src contains correct Rerun version', () => {
    render(<VisualizationPanel connected={true} />);
    const iframe = document.querySelector('iframe');
    expect(iframe?.src).toContain('version/0.33.1');
  });

  it('iframe src contains gRPC connection URL', () => {
    render(<VisualizationPanel connected={true} />);
    const iframe = document.querySelector('iframe');
    expect(iframe?.src).toContain('rerun+http://');
    expect(iframe?.src).toContain(':9876/proxy');
  });

  it('does not render iframe when disconnected', () => {
    render(<VisualizationPanel connected={false} />);
    const iframe = document.querySelector('iframe');
    expect(iframe).toBeNull();
  });
});
```

- [ ] **Step 9: Run VisualizationPanel tests**

```bash
cd frontend && npm test -- --reporter=verbose 2>&1 | grep -E "✓|✗|FAIL|PASS|VisualizationPanel"
```

Expected: all VisualizationPanel tests pass.

- [ ] **Step 10: Narrow App.test.tsx to app-level smoke test**

Replace `frontend/test/App.test.tsx`:

```tsx
import { describe, it, expect, vi } from 'vitest';
import { render, screen } from '@testing-library/react';
import App from '../src/App';

vi.spyOn(global, 'fetch').mockResolvedValue({
  json: () => Promise.resolve({ models: [{ id: 'dreamzero-v1', name: 'DreamZero', type: 'robotics' }] }),
} as Response);

describe('App', () => {
  it('renders the masthead with app title', () => {
    render(<App />);
    expect(screen.getByText('Robotics Playground')).toBeInTheDocument();
  });

  it('renders the chat panel', () => {
    render(<App />);
    expect(screen.getByText('Instructions')).toBeInTheDocument();
  });

  it('renders the simulation control panel', () => {
    render(<App />);
    expect(screen.getByText('Simulation Control')).toBeInTheDocument();
  });
});
```

- [ ] **Step 11: Run full frontend test suite**

```bash
cd frontend && npm test
```

Expected: all tests pass across all test files (~35+ tests).

- [ ] **Step 12: Verify lint + typecheck still pass**

```bash
make lint-frontend
```

Expected: no errors.

- [ ] **Step 13: Commit**

```bash
git add frontend/test/ frontend/package.json frontend/package-lock.json
git commit -m "test(frontend): add comprehensive component unit tests

Per-component test files for ChatPanel (interaction tests with
user-event), SimulationControlPanel (button state + callbacks),
PolicyBar (fetch mocking, loading/error states), VisualizationPanel
(iframe rendering, Rerun URL). App.test.tsx narrowed to smoke test.

Assisted-By: Claude <noreply@anthropic.com>"
```

---

### Task 5: Frontend Test Coverage — useSession Hook Tests

**Files:**

- Create: `frontend/test/useSession.test.ts`

**Interfaces:**

- Consumes: `useSession` hook from `src/hooks/useSession.ts`, `SessionState` and `ChatMessage` types
- Produces: hook-level tests exercising WebSocket connection, message dispatch, state updates, and cleanup via a mock WebSocket

- [ ] **Step 1: Create useSession hook tests**

`frontend/test/useSession.test.ts`:

```typescript
import { describe, it, expect, vi, beforeEach, afterEach } from 'vitest';
import { renderHook, act } from '@testing-library/react';
import { useSession } from '../src/hooks/useSession';

class MockWebSocket {
  static instances: MockWebSocket[] = [];
  readyState = 1; // OPEN
  onopen: (() => void) | null = null;
  onmessage: ((event: { data: string }) => void) | null = null;
  onclose: (() => void) | null = null;
  onerror: (() => void) | null = null;
  sent: string[] = [];

  constructor(public url: string) {
    MockWebSocket.instances.push(this);
    setTimeout(() => this.onopen?.(), 0);
  }

  send(data: string) {
    this.sent.push(data);
  }

  close() {
    this.readyState = 3;
    this.onclose?.();
  }

  simulateMessage(data: object) {
    this.onmessage?.({ data: JSON.stringify(data) });
  }
}

describe('useSession', () => {
  let originalWebSocket: typeof WebSocket;

  beforeEach(() => {
    MockWebSocket.instances = [];
    originalWebSocket = global.WebSocket;
    global.WebSocket = MockWebSocket as unknown as typeof WebSocket;
  });

  afterEach(() => {
    global.WebSocket = originalWebSocket;
  });

  it('starts disconnected', () => {
    const { result } = renderHook(() => useSession('test-session'));
    expect(result.current.connected).toBe(false);
  });

  it('connects to WebSocket with correct URL', () => {
    renderHook(() => useSession('test-session'));
    expect(MockWebSocket.instances).toHaveLength(1);
    expect(MockWebSocket.instances[0].url).toContain('/ws/sessions/test-session');
  });

  it('sets connected to true on open', async () => {
    const { result } = renderHook(() => useSession('test-session'));

    await act(async () => {
      await new Promise((r) => setTimeout(r, 10));
    });

    expect(result.current.connected).toBe(true);
  });

  it('updates session state on status message', async () => {
    const { result } = renderHook(() => useSession('test-session'));

    await act(async () => {
      await new Promise((r) => setTimeout(r, 10));
    });

    act(() => {
      MockWebSocket.instances[0].simulateMessage({
        type: 'status',
        state: 'running',
        step: 42,
        instruction: 'wave',
      });
    });

    expect(result.current.sessionState.state).toBe('running');
    expect(result.current.sessionState.step).toBe(42);
    expect(result.current.sessionState.instruction).toBe('wave');
  });

  it('adds ack messages to chat on instruction_ack', async () => {
    const { result } = renderHook(() => useSession('test-session'));

    await act(async () => {
      await new Promise((r) => setTimeout(r, 10));
    });

    act(() => {
      MockWebSocket.instances[0].simulateMessage({
        type: 'instruction_ack',
        status: 'received',
        text: 'wave',
      });
    });

    expect(result.current.messages).toHaveLength(1);
    expect(result.current.messages[0].role).toBe('system');
    expect(result.current.messages[0].text).toContain('received');
  });

  it('sendInstruction sends JSON and adds user message', async () => {
    const { result } = renderHook(() => useSession('test-session'));

    await act(async () => {
      await new Promise((r) => setTimeout(r, 10));
    });

    act(() => {
      result.current.sendInstruction('pick up block');
    });

    const sent = JSON.parse(MockWebSocket.instances[0].sent[0]);
    expect(sent.type).toBe('instruction');
    expect(sent.text).toBe('pick up block');

    expect(result.current.messages).toHaveLength(1);
    expect(result.current.messages[0].role).toBe('user');
    expect(result.current.messages[0].text).toBe('pick up block');
  });

  it('sendSimControl sends JSON with action', async () => {
    const { result } = renderHook(() => useSession('test-session'));

    await act(async () => {
      await new Promise((r) => setTimeout(r, 10));
    });

    act(() => {
      result.current.sendSimControl('play');
    });

    const sent = JSON.parse(MockWebSocket.instances[0].sent[0]);
    expect(sent.type).toBe('sim_control');
    expect(sent.action).toBe('play');
  });

  it('does not send when WebSocket is not open', () => {
    const { result } = renderHook(() => useSession('test-session'));

    act(() => {
      result.current.sendInstruction('wave');
    });

    expect(MockWebSocket.instances[0].sent).toHaveLength(0);
  });

  it('handles malformed WebSocket messages gracefully', async () => {
    const { result } = renderHook(() => useSession('test-session'));

    await act(async () => {
      await new Promise((r) => setTimeout(r, 10));
    });

    act(() => {
      MockWebSocket.instances[0].onmessage?.({ data: 'not json' });
    });

    expect(result.current.sessionState.state).toBe('idle');
  });

  it('defaults missing fields in status messages', async () => {
    const { result } = renderHook(() => useSession('test-session'));

    await act(async () => {
      await new Promise((r) => setTimeout(r, 10));
    });

    act(() => {
      MockWebSocket.instances[0].simulateMessage({ type: 'status' });
    });

    expect(result.current.sessionState.state).toBe('idle');
    expect(result.current.sessionState.step).toBe(0);
    expect(result.current.sessionState.instruction).toBe('');
  });

  it('cleans up WebSocket on unmount', async () => {
    const { result, unmount } = renderHook(() => useSession('test-session'));

    await act(async () => {
      await new Promise((r) => setTimeout(r, 10));
    });

    const ws = MockWebSocket.instances[0];
    unmount();
    expect(ws.readyState).toBe(3); // CLOSED
  });
});
```

- [ ] **Step 2: Run useSession tests**

```bash
cd frontend && npm test -- --reporter=verbose 2>&1 | grep -E "✓|✗|FAIL|PASS|useSession"
```

Expected: all useSession tests pass (~11 tests).

- [ ] **Step 3: Run full test suite**

```bash
make test
```

Expected: all frontend + backend tests pass.

- [ ] **Step 4: Commit**

```bash
git add frontend/test/useSession.test.ts
git commit -m "test(frontend): add useSession hook tests with WebSocket mock

Tests cover connection lifecycle, status message handling, instruction
sending, sim control dispatch, malformed message resilience, missing
field defaults, and cleanup on unmount.

Assisted-By: Claude <noreply@anthropic.com>"
```

---

### Task 6: End-to-End Verification + Container Smoke Test

**Files:**

- No file changes (verification-only task)

**Interfaces:**

- Consumes: all previous tasks — working `make lint`, `make test`, `make build`, `make compose-up`
- Produces: documented evidence that the Phase 1 milestone is met

- [ ] **Step 1: Run full lint suite**

```bash
make lint
```

Expected: frontend (eslint + typecheck) and backend (ruff check + ruff format) all pass.

- [ ] **Step 2: Run full test suite**

```bash
make test
```

Expected: all tests pass (frontend ~45+ tests, backend ~37+ tests).

- [ ] **Step 3: Build container images**

```bash
make build
```

Expected: both `robotics-playground-ui:local` and `robotics-playground:local` images build successfully.

- [ ] **Step 4: Start Podman Compose stack**

```bash
make compose-up
sleep 5
```

Expected: both containers start.

- [ ] **Step 5: Verify backend health**

```bash
curl -s http://localhost:8000/api/health | python3 -c "import sys,json; d=json.load(sys.stdin); assert d=={'status':'ok'}, d; print('Backend health: OK')"
```

Expected: `Backend health: OK`

- [ ] **Step 6: Verify model listing**

```bash
curl -s http://localhost:8000/api/models?type=robotics | python3 -c "import sys,json; d=json.load(sys.stdin); assert len(d['models'])>=1; print(f'Models: {len(d[\"models\"])} found')"
```

Expected: `Models: 1 found`

- [ ] **Step 7: Verify frontend serves**

```bash
curl -s http://localhost:8080/index.html | head -c 200
curl -s -o /dev/null -w "%{http_code}" http://localhost:8080/remoteEntry.js
```

Expected: HTML content returned, remoteEntry.js returns 200.

- [ ] **Step 8: Verify frontend API proxy**

```bash
curl -s http://localhost:8080/api/health | python3 -c "import sys,json; d=json.load(sys.stdin); assert d=={'status':'ok'}; print('Frontend proxy to backend: OK')"
```

Expected: `Frontend proxy to backend: OK` (proves nginx `/api/` proxy works).

- [ ] **Step 9: Stop Compose stack**

```bash
make compose-down
```

- [ ] **Step 10: Document results**

If all checks pass, the Phase 1 milestone is met:

- User opens playground at `:8080`, sees the layout (sidebar + main area)
- Backend serves mock data and responds to WebSocket messages
- Container images build and compose stack runs
- Frontend proxies API requests to backend

Note: verifying the Rerun viewer visually (camera feed + joint plots in browser) requires opening a browser with the dev server running (`make dev-frontend` + `make dev-backend` in separate terminals). This is a manual verification step. If the Rerun viewer iframe does not connect, the most likely cause is a version mismatch or CORS issue — document the finding.

---

### Task 7: Hummingbird + Rerun SDK Compatibility Spike

**Files:**

- Create: `docs/spikes/2026-07-03-hummingbird-rerun-compatibility.md` (spike results)

**Interfaces:**

- Consumes: `backend/Containerfile`, Rerun SDK 0.33
- Produces: documented spike results — whether Rerun SDK runs in `hi/python:3.14` distroless container, what workarounds are needed, and assessment of ROS 2 client options for Phase 2

- [ ] **Step 1: Test Rerun SDK import in backend container**

```bash
podman build -t robotics-playground:spike -f backend/Containerfile backend/
podman run --rm robotics-playground:spike python -c "import rerun; print(f'Rerun {rerun.__version__} OK')"
```

Expected: either succeeds (Rerun works in distroless) or fails with a specific error (missing native lib, glibc issue, etc.).

- [ ] **Step 2: Test Rerun gRPC server startup in container**

```bash
podman run --rm -p 9877:9876 robotics-playground:spike python -c "
import rerun as rr
rr.init('test')
rr.serve_grpc(grpc_port=9876)
print('Rerun gRPC server started OK')
import time; time.sleep(2)
"
```

Expected: either starts successfully or fails with a specific error.

- [ ] **Step 3: Assess ROS 2 client options**

Research and document:

1. Can `rclpy` (native ROS 2 Python) install in `hi/python:3.14` (no RPM manager)?
2. Is there a pure-Python DDS/ROS 2 client that avoids native deps?
3. What's the multi-stage build approach if native deps are needed?

- [ ] **Step 4: Document spike results**

Create `docs/spikes/2026-07-03-hummingbird-rerun-compatibility.md`:

```markdown
# Spike: Hummingbird + Rerun SDK Compatibility

**Date:** 2026-07-03
**Status:** [PASS/FAIL/PARTIAL]

## Rerun SDK on hi/python:3.14

### Import Test
[Results from step 1]

### gRPC Server Test
[Results from step 2]

### Workarounds Required
[Any patches, env vars, or alternative base images needed]

## ROS 2 Client Options for Phase 2

| Option | Feasibility | Notes |
|--------|-------------|-------|
| rclpy on hi/python:3.14 | [Yes/No] | [Details] |
| Pure-Python DDS client | [Yes/No] | [Details] |
| Multi-stage build with builder | [Yes/No] | [Details] |
| UBI9 Python base (fallback) | Yes | Always works but loses distroless benefits |

## Recommendation

[Which approach to use for Phase 2 Robot/Sim Bridge implementation]
```

- [ ] **Step 5: Commit**

```bash
git add docs/spikes/
git commit -m "docs: add Hummingbird + Rerun SDK compatibility spike results

Document whether Rerun SDK works in hi/python:3.14 distroless
container and assess ROS 2 client options for Phase 2.

Assisted-By: Claude <noreply@anthropic.com>"
```
