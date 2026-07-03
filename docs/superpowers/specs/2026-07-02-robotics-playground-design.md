# Robotics Playground — Design Spec

## Product Concept

The **Robotics Playground** is an interactive web application within the Physical AI Studio that lets users experiment with robot policy models (VLAs, world-action models) by connecting them to robots — simulated or physical — and issuing natural language instructions in a conversational loop.

It is the robotics analog of OpenShift AI's Gen AI Studio LLM Playground: where the LLM playground lets users select a language model and chat with it, the Robotics Playground lets users select a robot policy model, connect it to a robot (simulated or physical), and instruct it via natural language while watching the robot execute in real time.

### Core User Flow

1. **Configure session** — Select a policy model (e.g., DreamZero), a robot connection (Isaac Sim instance, physical robot endpoint), and optionally a simulation scene (USD file)
2. **Observe** — See live camera feeds from the robot (observation cameras + optional virtual cameras from sim)
3. **Instruct** — Type a natural language instruction in the chat panel (e.g., "Pick up the red block and place it on the blue plate")
4. **Watch** — The policy model receives observations, generates actions, the robot executes them. The user watches in real-time via camera views and telemetry overlays (action trajectories, joint states, model internals)
5. **Iterate** — Give follow-up instructions based on what happened. The chat history provides context for multi-step tasks
6. **Control** — At any time, pause/resume/reset the simulation, adjust sim speed, step manually, or switch to manual teleoperation ("human-as-VLA")

### Comparison Mode

Following the Gen AI Studio pattern, the user starts with a single policy in full-width view and can dynamically split the output area to add a second policy for side-by-side comparison. Both policies receive the same instruction and start from identical initial conditions, but each controls its own simulation environment — so observations diverge as each policy takes different actions. The user can compare execution quality, timing, and model behavior.

### Differentiators

- **No comparable offering from NVIDIA** — NVIDIA has API playgrounds (build.nvidia.com) and Isaac Sim WebRTC streaming, but no multi-tenant, web-based robotics playground for interactive VLA experimentation
- **Model-agnostic** via OpenPI protocol (not locked to GR00T or any specific model family)
- **Sim/robot-agnostic** via ROS 2 (not locked to Isaac Sim)
- **Integrated** into the governed RHOAI platform (model catalog, access control) when deployed on OpenShift AI, but also runs standalone on vanilla Kubernetes

## Architecture

Three layers: **frontend** (browser), **backend** (orchestration proxy), **external services** (policy servers, robots/simulators).

### System Diagram

```text
┌──────────────────────────────────────────────────────────┐
│  Browser (PatternFly Shell)                              │
│  ┌──────────────┐  ┌──────────────────────────────────┐  │
│  │ Chat Panel   │  │ Rerun Viewer (WASM)              │  │
│  │              │  │ • Camera views (obs + virtual)   │  │
│  │              │  │ • Action trajectories            │  │
│  │              │  │ • Model "thinking" overlays      │  │
│  │              │  │ • Joint state timelines          │  │
│  ├──────────────┤  ├──────────────────────────────────┤  │
│  │ Session      │  │ Control Bar                      │  │
│  │ Setup +      │  │ Play/Pause/Reset/Step | Speed    │  │
│  │ Model Select │  │ Manual control toggle            │  │
│  └──────────────┘  └──────────────────────────────────┘  │
└──────────────────────────────────────────────────────────┘
         │ WebSocket / REST              │ WebSocket
         ▼                               ▼ (Rerun stream)
┌──────────────────────────────────────────────────────────┐
│  Playground Backend (Python)                             │
│                                                          │
│  ┌──────────────┐  ┌──────────────┐  ┌───────────────┐   │
│  │ Session Mgr  │  │ Policy       │  │ Robot/Sim     │   │
│  │              │  │ Bridge       │  │ Bridge        │   │
│  │ • lifecycle  │  │ • OpenPI     │  │ • ROS 2 node  │   │
│  │ • multi-user │  │   client(s)  │  │ • obs topics  │   │
│  │ • state      │  │ • action     │  │ • cmd topics  │   │
│  │              │  │   dispatch   │  │ • sim control │   │
│  └──────┬───────┘  └──────┬───────┘  └──────┬────────┘   │
│         │                 │                 │            │
│  ┌──────▼─────────────────▼─────────────────▼────────┐   │
│  │ Rerun Logger                                      │   │
│  │ • logs obs frames, actions, joint states, model   │   │
│  │   telemetry as Rerun entities                     │   │
│  │ • serves Rerun web viewer data via WebSocket      │   │
│  └───────────────────────────────────────────────────┘   │
└──────────────────────────────────────────────────────────┘
         │ OpenPI                         │ ROS 2
         ▼                                ▼
┌─────────────────┐             ┌─────────────────┐
│ VLA Server      │             │ Isaac Sim       │
│ (vLLM-Omni /    │             │ or Physical     │
│  DreamZero)     │             │ Robot           │
└─────────────────┘             └─────────────────┘
```

### Frontend (React + PatternFly + Rerun)

A Module Federation micro-frontend that can be loaded into the RHOAI dashboard or run standalone.

**Information elements** (layout left to UX/design specialist):

- **Session Setup** — Model selector (from MaaS catalog or local config), robot/sim connection config, scene selector
- **Chat Panel** — Conversational instruction interface with message history. Each user message becomes an instruction to the active policy. System messages show status ("Executing...", "Completed (4.2s)", "Error")
- **Visualization Area** — Embedded Rerun web viewer showing camera feeds, action trajectories, joint state timelines, model telemetry. In comparison mode, the visualization area splits to show both policies; all other elements stay in place
- **Control Bar** — Simulation controls (play/pause/reset/step, speed slider), manual teleoperation toggle

**Design principles**:

- Follow PatternFly design language and Gen AI Studio patterns as reference
- Layout structure stays fixed when switching between single and comparison mode — only the visualization area splits
- Leave detailed layout decisions to a UX/design pass

### Backend (Python, Orchestration Proxy)

Python chosen for native ROS 2 support (`rclpy`) and native OpenPI client libraries.

**Session Manager** (`session_manager.py`):

- Creates/destroys sessions via REST API
- Each session owns: one Robot/Sim Bridge, one or more Policy Bridges, one Rerun Logger instance
- Tracks session state (`SETUP → CONNECTED → RUNNING ↔ PAUSED ↔ MANUAL → ENDED`)
- Handles WebSocket connections from the browser — routes instructions to policy bridges, forwards status events back
- Enforces session limits (max concurrent sessions, timeouts)

**Policy Bridge** (`policy_bridge.py`):

- OpenPI client (WebSocket + msgpack) communicating with VLA policy servers
- On each observation cycle: packs current observation + active instruction into OpenPI request, sends to server, receives action tensor
- Handles vLLM-Omni session management API (when available) for multi-turn context
- In comparison mode: N instances, each with its own server connection, all receiving the same observations
- Logs predicted actions and model telemetry to Rerun Logger

**Robot/Sim Bridge** (`robot_sim_bridge.py`):

- ROS 2 node subscribing to observation topics (`sensor_msgs/Image`, `sensor_msgs/JointState`)
- Publishes action commands (`trajectory_msgs/JointTrajectory`)
- Sim control via `isaacsim.ros2.sim_control` services (play/pause/reset/step, speed)
- Translates between OpenPI action tensor format and ROS 2 message types (leveraging `lerobot-ros` or equivalent)
- In comparison mode: routes actions to the correct sim environment

**Rerun Logger** (`rerun_logger.py`):

- Central telemetry sink
- Receives data from all bridges, logs as typed Rerun entities
- Runs a Rerun WebSocket server per session for the browser viewer
- Manages `policy_0/`, `policy_1/` namespacing (always indexed, even with single policy)
- Timestamps all data using shared session clock (sim time when available, wall clock otherwise)

### External Services

- **Policy servers** — vLLM-Omni (DreamZero, future VLAs) or any OpenPI-compatible server. Discovered via MaaS catalog (RHOAI) or local configuration (standalone)
- **Robot/Simulator** — Any ROS 2-speaking robot or simulator. Isaac Sim via its native ROS 2 bridge. Physical robots via standard ROS 2 interfaces

## Protocol & Data Flow

### Protocol Boundaries

| Boundary | Protocol | Data Format |
| ---------- | ---------- | ------------- |
| Backend ↔ Policy Server | OpenPI (WebSocket + msgpack) | Observations in, action tensors out |
| Backend ↔ Robot/Sim | ROS 2 (DDS) | `sensor_msgs/Image`, `sensor_msgs/JointState`, `trajectory_msgs/JointTrajectory` |
| Backend ↔ Sim Control | ROS 2 services | `isaacsim.ros2.sim_control` (play/pause/reset/step) |
| Backend ↔ Browser (viz) | WebSocket | Rerun data stream (Arrow IPC) |
| Backend ↔ Browser (control) | REST + WebSocket | JSON |
| Browser ↔ MaaS Catalog | REST | JSON (when deployed in RHOAI) |

### Observation-Action Loop

```text
  Isaac Sim / Robot                Backend                    Browser
       │                             │                          │
       │── ROS 2 topics ────────────►│                          │
       │  camera frames, joint state │                          │
       │                             │                          │
       │                      Robot/Sim Bridge                  │
       │                        │         │                     │
       │                        │    Rerun Logger ──WebSocket──►│
       │                        │    (log frames,    (viewer)   │
       │                        │     joints)                   │
       │                        ▼                               │
       │                   Policy Bridge                        │
       │                        │                               │
       │                   OpenPI request                       │
       │                        ▼                               │
       │                   VLA Server                           │
       │                        │                               │
       │                   action tensor                        │
       │                        │                               │
       │◄── ROS 2 commands ─────┘                               │
       │  joint trajectory                                      │
```

### Instruction Flow

1. Browser sends instruction text + session ID over WebSocket
2. Session Manager attaches instruction to active policy session(s)
3. Policy Bridge includes instruction in every subsequent OpenPI observation payload as language conditioning
4. Instruction persists until user sends a new one or clears it
5. Rerun Logger logs instruction as TextLog annotation at current timestamp
6. Browser shows instruction in chat panel with execution status updates

In comparison mode, step 3 fans out to all policy bridges with the same instruction.

### Manual Control Flow

When manual mode is active:

- Policy Bridge is bypassed — no actions sent to VLA
- Browser sends control inputs over WebSocket to backend
- Robot/Sim Bridge translates to ROS 2 joint commands
- Observations continue streaming and logging
- Switching back to VLA mode re-engages the Policy Bridge from current robot state

### Session Lifecycle

```
SETUP → CONNECTED → RUNNING ↔ PAUSED → ENDED
                       ↕
                    MANUAL
```

## Rerun Integration

Rerun serves as the unified visualization layer. The backend logs all telemetry as Rerun entities; the browser renders via Rerun's embedded web viewer (`@rerun-io/web-viewer-react` or `<iframe>`).

### Entity Tree

```text
session/
├── policy_0/                 # Always indexed, even with single policy
│   ├── camera/
│   │   ├── wrist             # Observation camera (Image)
│   │   ├── head              # Additional robot camera (Image)
│   │   └── overview          # Virtual observer camera, sim only (Image)
│   ├── actions/
│   │   ├── predicted         # Raw action tensor (Tensor)
│   │   └── trajectory        # Trajectory overlay (LineStrips3D)
│   ├── joints/
│   │   ├── positions         # Joint angle time series (Scalar)
│   │   ├── velocities        # Joint velocity time series (Scalar)
│   │   └── commands          # Commanded targets (Scalar)
│   ├── end_effector/
│   │   └── pose              # End-effector position (Transform3D)
│   ├── telemetry/
│   │   ├── inference_ms      # Per-step latency (Scalar)
│   │   └── confidence        # Model confidence if available (Scalar)
│   ├── internals/            # "Model thinking" — optional, model-dependent
│   │   ├── attention_map     # Attention heatmap (Image)
│   │   └── embeddings        # Latent space projection (Points3D)
│   └── sim/                  # Per-environment sim state (sim only)
│       ├── scene/
│       │   └── objects       # Scene object poses (Boxes3D, Transform3D)
│       └── status/
│           ├── sim_time      # Simulation timestamp (Scalar)
│           └── step_count    # Step counter (Scalar)
│
├── policy_1/                 # Present in comparison mode
│   └── ...                   # Same structure as policy_0
│
└── instructions/             # Chat instruction annotations (TextLog)
```

### Data Logging

| Data | Source | Rate | Rerun Type | Purpose |
| ------ | -------- | ------ | ------------ | --------- |
| Camera frames | ROS 2 image topics | ~10-30 Hz | `Image` | What the model sees / overview |
| Joint states | ROS 2 joint topics | ~10-30 Hz | `Scalar` (per joint) | Robot state timeline |
| Predicted actions | OpenPI response | Per inference | `Scalar` + `LineStrips3D` | Action visualization |
| Inference latency | Policy Bridge | Per inference | `Scalar` | Performance monitoring |
| Instructions | User chat input | On user action | `TextLog` | Timeline annotation |
| Model internals | OpenPI response (optional) | Per inference, if available | `Image` / `Points3D` | "Thinking" visualization |

### Model "Thinking" — Three Tiers

1. **Always available** (standard OpenPI): Predicted action trajectory, inference latency
2. **Model-dependent**: Attention maps, confidence scores — logged when present, absent entities simply don't appear in viewer
3. **Requires protocol extension**: Latent embeddings, CEM trajectory bundles — out of scope for MVP, entity tree has reserved paths

## Backend API Surface

### REST (Session Management)

| Method | Path | Purpose |
| -------- | ------ | --------- |
| `POST` | `/api/sessions` | Create session (model, robot/sim config, scene) |
| `GET` | `/api/sessions/{id}` | Get session state and metadata |
| `DELETE` | `/api/sessions/{id}` | Tear down session |
| `POST` | `/api/sessions/{id}/policies` | Add a policy (comparison mode) |
| `DELETE` | `/api/sessions/{id}/policies/{idx}` | Remove a policy |
| `GET` | `/api/models?type=robotics` | List available robotics models |

### WebSocket (`/ws/sessions/{id}`)

| Direction | Type | Payload |
| ----------- | ------ | --------- |
| Client → Server | `instruction` | `{text: string}` |
| Client → Server | `sim_control` | `{action: "play"\|"pause"\|"reset"\|"step", speed?: number}` |
| Client → Server | `manual_control` | `{joint_targets: number[]}` or `{ee_delta: number[]}` |
| Client → Server | `mode_switch` | `{mode: "vla"\|"manual"}` |
| Server → Client | `status` | `{state: string, policy_0?: {...}, policy_1?: {...}}` |
| Server → Client | `instruction_ack` | `{instruction_id, status: "received"\|"executing"\|"completed"\|"error"}` |
| Server → Client | `error` | `{code: string, message: string}` |

Rerun data streams over a separate WebSocket managed by Rerun's server.

## Deployment

### Two-Repo Model

| Repo | Contains | Purpose |
|------|----------|---------|
| [`github.com/redhat-et/robotics-playground`](https://github.com/redhat-et/robotics-playground) | Frontend, Backend, Containerfiles, standalone Kustomize | The product — runs on vanilla K8s |
| [`github.com/redhat-et/physical-ai-platform-demo`](https://github.com/redhat-et/physical-ai-platform-demo) | RHOAI integration: federation config, deployment manifests, MaaS wiring | The glue — deploys into RHOAI |

### Standalone Assumptions (Playground Repo)

- UI and backend are in the **same namespace** (no cross-namespace assumptions)
- UI container exposes `/remoteEntry.js` for RHOAI plugin integration **and** works as a standalone SPA
- No dependency on RHOAI APIs for core functionality — model list from MaaS catalog (when available) or local config (standalone)
- No hardcoded namespace in any manifest

### Container Images

| Image | Base | Contents |
|-------|------|----------|
| `quay.io/redhat-et/robotics-playground-ui` | `registry.access.redhat.com/hi/nginx:latest` | Compiled webpack assets |
| `quay.io/redhat-et/robotics-playground` | `registry.access.redhat.com/hi/python:3.14` | Python backend |

**Hummingbird constraint**: The distroless `hi/python:3.14` image cannot install RPMs. ROS 2 `rclpy` requires native libraries. Options if this blocks:

1. **Preferred**: Pure-Python DDS/ROS 2 client
2. **Fallback**: Multi-stage build with `hi/python:3.14-builder` for native compilation
3. **Last resort**: UBI9 Python base for backend only

This is a key technical spike for Phase 1.

### Repository Structure

```text
robotics-playground/
├── frontend/
│   ├── src/
│   ├── package.json
│   ├── tsconfig.json
│   ├── webpack.config.js
│   └── Containerfile
├── backend/
│   ├── src/
│   │   └── robotics_playground/
│   ├── pyproject.toml
│   └── Containerfile
├── deploy/
│   ├── kustomize/              # Standalone K8s deployment
│   └── compose.yaml            # Podman Compose for local testing
├── docs/
├── Makefile
├── CLAUDE.md
├── LICENSE                     # Apache 2.0
└── README.md
```

### Local Development with Podman Compose

`deploy/compose.yaml` deploys both frontend and backend containers locally for integration testing:

- `robotics-playground-ui` — nginx serving frontend on port 8080
- `robotics-playground` — Python backend on port 8000
- Frontend proxies API/WebSocket requests to backend (nginx config)

### CI (GitHub Actions)

- **Lint + Type Check**: `eslint` + `tsc --noEmit` (frontend), `ruff` (backend), `yamllint` (manifests)
- **Unit Tests**: `vitest` (frontend), `pytest` (backend)
- **Container Build (multi-arch)**: Build both images on native runners for `amd64` and `arm64`. Per-arch image tags: `${arch}-${commit_sha}`. On merge to `main`, push per-arch images and assemble a multi-arch manifest list. On release tags, additionally tag `${arch}-${git_tag}` and `${arch}-latest`, and push a manifest list for each.
- **Manifest Validate**: Render Kustomize manifests and validate with `kubeconform`

### Developer Workflow

- `make dev` — frontend webpack dev server + backend with hot reload
- `make build` — build both container images
- `make test` — all tests
- `make lint` — all linters
- `make validate` — validate deploy manifests
- `make compose-up` / `make compose-down` — run/stop Podman Compose stack

### Testing & Quality Discipline

- **Tests first**: write tests before implementation code
- **Gate on green**: run tests, linting, and validation before every commit; fix all errors and warnings
- **Container verification**: always build container images, run the Podman Compose deployment, and verify the service is functional — unit tests passing alone is not sufficient
- **Test integrity**: tests may only be modified when the test logic is clearly flawed, not to make failures go away

### Implementation Parallelism

Frontend and backend can be implemented in parallel by sub-agents once the API contract (REST + WebSocket protocol from the Backend API Surface section) is defined. Each sub-agent works against the shared protocol spec and mock data. Integration testing via Podman Compose validates that the pieces fit together.

## Phased Implementation

### Phase 0: Repository Bootstrap + CI

Stand up `github.com/redhat-et/robotics-playground` with project structure, build tooling, and CI.

- Initialize repo with directory structure, `LICENSE`, `CLAUDE.md`, `Makefile`
- Frontend: scaffold from existing `features/robotics-playground/` in platform-demo repo
- Backend: initialize Python project with `pyproject.toml`
- Containerfiles for both images (Hummingbird bases)
- GitHub Actions workflows: lint, test, multi-arch container build (native runners, `${arch}-${commit_sha}` tags, manifest lists), manifest validate
- Standalone Kustomize base in `deploy/kustomize/`
- Podman Compose file in `deploy/compose.yaml`
- `make dev` / `make build` / `make test` / `make lint` / `make validate` / `make compose-up` / `make compose-down` targets

### Phase 1: Skeleton — UI Shell + Mock Backend

End-to-end data flow with mock data. Validates architecture and developer workflow.

- PatternFly page structure: session setup, chat panel, visualization area, control bar
- Embedded Rerun web viewer connected to backend WebSocket
- Model selector (hardcoded list in standalone mode)
- Chat input sends instructions, receives status updates
- Mock Robot/Sim Bridge: synthetic observations (static images, sinusoidal joints) at 10 Hz
- Mock Policy Bridge: random action tensors with fixed latency
- Rerun Logger: logs mock data to entity tree
- **Technical spike**: validate Hummingbird + Rerun SDK compatibility, assess ROS 2 client options

**Milestone**: User opens playground, sees mock camera feed and joint plots in Rerun, types instruction, sees mock status. No GPU required.

### Phase 2: ROS 2 + Isaac Sim Integration

Replace mock bridges with real ROS 2 communication to Isaac Sim.

- Real Robot/Sim Bridge as ROS 2 node
- Subscribe to Isaac Sim camera/joint topics, publish joint commands
- Sim control via `isaacsim.ros2.sim_control` (play/pause/reset/step, speed)
- Scene selector for USD files
- Manual teleoperation mode
- Virtual camera support (overview camera from Isaac Sim)
- Resolve Hummingbird vs UBI base image based on Phase 1 spike

**Milestone**: User connects to running Isaac Sim, sees real camera feeds, can pause/reset/step sim and manually control robot.

### Phase 3: VLA Policy Integration

Connect a real VLA policy server via OpenPI.

- Real Policy Bridge with OpenPI client
- DreamZero on vLLM-Omni as first supported model
- End-to-end instruction flow: user instruction → OpenPI → action → ROS 2 → sim
- Model telemetry logging (inference latency, predicted trajectory)
- vLLM-Omni session management API integration (when available)
- MaaS catalog integration for model discovery (RHOAI deployment)

**Milestone**: User selects DreamZero, connects to Isaac Sim, types "pick up the red block," watches robot execute autonomously.

### Phase 4: Comparison Mode + Polish

Side-by-side policy comparison and production readiness.

- Dynamic split (Gen AI Studio pattern) to add second policy
- Dual sim environments with synced initial conditions
- Shared instruction dispatch
- Per-policy Rerun entity trees (`policy_0/`, `policy_1/`)
- Model "thinking" visualization for models that expose internals
- Session timeout/cleanup, error handling, reconnection

**Milestone**: User compares DreamZero vs another VLA side-by-side on same task.

### Phase 5: Physical Robot Support

Connect to physical robots using the same ROS 2 interface.

- Physical robot connection flow in session setup
- Safety controls (e-stop, workspace limits, velocity caps)
- Latency-aware observation loop
- Camera calibration utilities

**Milestone**: Same playground UI controls a physical robot arm, demonstrating sim-to-real parity.

## Key Technical Risks

| Risk | Impact | Mitigation |
| ------ | -------- | ------------ |
| ROS 2 `rclpy` incompatible with Hummingbird distroless | Backend container can't use preferred base image | Phase 1 spike; fallback to multi-stage build or UBI9 |
| Rerun WASM viewer performance with high-rate camera streams | Laggy visualization in browser | Throttle frame logging rate, compress images, use Rerun's built-in decimation |
| OpenPI protocol doesn't expose model internals | "Thinking" visualization limited to basic actions | Tier 1 (actions + latency) always works; internals are progressive enhancement |
| Isaac Sim single-user per instance | Comparison mode needs two instances | Use Isaac Lab vectorized envs or manage instance pool |
| vLLM-Omni session management API not yet stable | Multi-turn instruction context may be limited | Fall back to stateless per-observation instruction injection |

## NVIDIA Landscape (Competitive Context)

NVIDIA does not offer a comparable multi-tenant web-based robotics playground. Their closest offerings:

- **build.nvidia.com** — API playgrounds for Cosmos Reasoner (prompt + image → reasoning text) and GR00T Blueprint (synthetic motion generation). Simple form UX, no live simulation.
- **Isaac Sim WebRTC** — Full 3D sim streamed to browser. High fidelity but single-user, GPU-heavy, not a "playground."
- **GR00T N1** — No interactive playground. Jupyter notebooks only.
- **Isaac Lab-Arena** — Batch policy evaluation tool. No browser UI.

The Robotics Playground fills a gap: a multi-tenant, model-agnostic, web-based environment for interactive VLA experimentation.
