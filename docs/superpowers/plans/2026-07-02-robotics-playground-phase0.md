# Robotics Playground — Phase 0: Repository Bootstrap + CI

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Stand up the `github.com/redhat-et/robotics-playground` repository with working frontend scaffold, backend skeleton, container builds, Podman Compose, Kustomize manifests, and multi-arch CI — ready for Phase 1 feature implementation.

**Architecture:** Two-container application: React/PatternFly frontend served by nginx, Python/FastAPI backend. Both built as multi-arch container images on Hummingbird base images. Deployed via Podman Compose (local) or Kustomize (K8s).

**Tech Stack:**

- Frontend: React 18, PatternFly 6, TypeScript 5, Webpack 5 (Module Federation), ESLint 9, Vitest
- Backend: Python 3.14, FastAPI, Uvicorn, Ruff, Pytest
- Containers: `hi/nginx:latest` (frontend), `hi/python:3.14` (backend)
- CI: GitHub Actions, Podman, multi-arch native runners

## Global Constraints

- Apache 2.0 license
- No hardcoded namespaces in K8s manifests
- Frontend exposes `/remoteEntry.js` for RHOAI plugin integration AND works standalone
- Frontend and backend assume same-namespace deployment
- Conventional Commits for commit messages
- YAML: 2-space indent
- Tests first: write tests before implementation, run tests + linting + validation before committing
- Container verification: build images and run Podman Compose before declaring a task complete

## File Map

```text
robotics-playground/
├── .github/
│   └── workflows/
│       ├── ci.yaml                     # Lint + test on every PR
│       ├── containers.yaml             # Multi-arch container build + push
│       └── validate-manifests.yaml     # Kustomize + kubeconform
├── frontend/
│   ├── src/
│   │   ├── index.ts                    # Webpack entry (dynamic import bootstrap)
│   │   ├── bootstrap.tsx               # React root mount (standalone mode)
│   │   ├── App.tsx                     # Top-level app component with routes
│   │   ├── extensions.ts               # RHOAI Module Federation extensions
│   │   ├── RoboticsPlayground.tsx      # Main playground page component
│   │   └── PhysicalAiStudioNavIcon.ts  # Custom nav icon SVG
│   ├── test/
│   │   └── App.test.tsx                # Smoke test for App component
│   ├── package.json
│   ├── tsconfig.json
│   ├── webpack.config.js
│   ├── eslint.config.mjs
│   ├── nginx.conf                      # nginx config for container
│   └── Containerfile
├── backend/
│   ├── src/
│   │   └── robotics_playground/
│   │       ├── __init__.py
│   │       ├── main.py                 # FastAPI app + health endpoint
│   │       └── config.py               # Settings via pydantic-settings
│   ├── tests/
│   │   ├── __init__.py
│   │   └── test_health.py              # Health endpoint test
│   ├── pyproject.toml                  # Project config (deps, ruff, pytest)
│   └── Containerfile
├── deploy/
│   ├── compose.yaml                    # Podman Compose (ui + backend)
│   └── kustomize/
│       ├── kustomization.yaml
│       ├── ui-deployment.yaml
│       ├── ui-service.yaml
│       ├── backend-deployment.yaml
│       └── backend-service.yaml
├── Makefile
├── CLAUDE.md
├── LICENSE
├── README.md
└── .gitignore
```

---

### Task 1: Repository Init + Frontend Scaffold

**Files:**

- Create: `LICENSE`, `README.md`, `CLAUDE.md`, `.gitignore`
- Create: `frontend/package.json`, `frontend/tsconfig.json`, `frontend/webpack.config.js`, `frontend/eslint.config.mjs`
- Create: `frontend/src/index.ts`, `frontend/src/bootstrap.tsx`, `frontend/src/App.tsx`, `frontend/src/extensions.ts`, `frontend/src/RoboticsPlayground.tsx`, `frontend/src/PhysicalAiStudioNavIcon.ts`
- Create: `frontend/test/App.test.tsx`
- Create: `Makefile` (partial — frontend targets only)

**Interfaces:**

- Produces: `frontend/` directory with buildable, lintable, testable React project. `npm run build` outputs `dist/` with `remoteEntry.js`. Exported extensions array from `./extensions` for RHOAI Module Federation.

**Prerequisites:** The user has created the empty repo at `github.com/redhat-et/robotics-playground` and cloned it locally. All steps below are run from the repo root.

- [ ] **Step 1: Create repo boilerplate files**

`.gitignore`:

```text
node_modules/
dist/
__pycache__/
*.egg-info/
.ruff_cache/
.pytest_cache/
.venv/
*.pyc
```

`LICENSE`: Apache 2.0 (full text from <https://www.apache.org/licenses/LICENSE-2.0.txt>)

`README.md`:

```markdown
# Robotics Playground

An interactive web application for experimenting with robot policy models (VLAs, world-action models) by connecting them to simulated or physical robots.

Part of the [Physical AI Studio](https://github.com/redhat-et/physical-ai-platform-demo).

## Development

```bash
make dev          # Start frontend + backend dev servers
make test         # Run all tests
make lint         # Run all linters
make build        # Build container images
make compose-up   # Start Podman Compose stack
make compose-down # Stop Podman Compose stack
make validate     # Validate Kustomize manifests
```

## License

Apache 2.0

```

`CLAUDE.md`:
```markdown
# CLAUDE.md

## Project Overview

Robotics Playground — interactive web app for experimenting with robot policy models (VLAs).
Two containers: React/PatternFly frontend (nginx) + Python/FastAPI backend (orchestration proxy).

## Repository Layout

- `frontend/` — React 18 + PatternFly 6 + Module Federation micro-frontend
- `backend/` — Python/FastAPI orchestration proxy
- `deploy/compose.yaml` — Podman Compose for local testing
- `deploy/kustomize/` — Standalone K8s deployment manifests

## Conventions

- Conventional Commits for commit messages
- YAML: 2-space indent
- Tests first: write tests before implementation
- Always run `make lint`, `make test`, `make build` before committing

## Development

- `make dev` — start frontend (webpack dev server :9200) + backend (uvicorn :8000)
- `make test` — run all tests (vitest + pytest)
- `make lint` — run all linters (eslint + ruff + yamllint)
- `make build` — build container images with Podman
- `make compose-up` / `make compose-down` — Podman Compose stack
- `make validate` — validate Kustomize manifests with kubeconform
```

- [ ] **Step 2: Create frontend package.json**

`frontend/package.json`:

```json
{
  "name": "@robotics-playground/frontend",
  "version": "0.0.1",
  "private": true,
  "scripts": {
    "build": "webpack --mode production",
    "dev": "webpack serve --mode development --port 9200",
    "test": "vitest run",
    "test:watch": "vitest",
    "lint": "eslint src/ test/",
    "typecheck": "tsc --noEmit"
  },
  "dependencies": {
    "react": "^18.3.1",
    "react-dom": "^18.3.1",
    "react-router-dom": "^6.28.0",
    "@patternfly/react-core": "^6.3.0",
    "@patternfly/react-icons": "^6.3.0"
  },
  "devDependencies": {
    "@module-federation/enhanced": "^0.18.4",
    "@testing-library/react": "^16.1.0",
    "@testing-library/jest-dom": "^6.6.3",
    "@types/react": "^18.3.1",
    "@types/react-dom": "^18.3.1",
    "css-loader": "^7.1.2",
    "eslint": "^9.17.0",
    "@eslint/js": "^9.17.0",
    "typescript-eslint": "^8.18.0",
    "jsdom": "^25.0.1",
    "style-loader": "^4.0.0",
    "ts-loader": "^8.0.5",
    "typescript": "^5.7.3",
    "vitest": "^3.0.0",
    "webpack": "5.104.1",
    "webpack-cli": "^5.1.4",
    "webpack-dev-server": "^5.2.4"
  }
}
```

- [ ] **Step 3: Create frontend config files**

`frontend/tsconfig.json`:

```json
{
  "compilerOptions": {
    "target": "ES2020",
    "module": "ESNext",
    "moduleResolution": "bundler",
    "jsx": "react-jsx",
    "strict": true,
    "esModuleInterop": true,
    "skipLibCheck": true,
    "outDir": "dist"
  },
  "include": ["src", "test"]
}
```

`frontend/webpack.config.js`:

```javascript
const { ModuleFederationPlugin } = require('@module-federation/enhanced/webpack');
const path = require('path');
const deps = require('./package.json').dependencies;

module.exports = {
  entry: './src/index',
  output: {
    path: path.resolve(__dirname, 'dist'),
    publicPath: 'auto',
    clean: true,
  },
  resolve: {
    extensions: ['.ts', '.tsx', '.js'],
  },
  module: {
    rules: [
      {
        test: /\.tsx?$/,
        use: 'ts-loader',
        exclude: /node_modules/,
      },
      {
        test: /\.css$/,
        use: ['style-loader', 'css-loader'],
      },
    ],
  },
  plugins: [
    new ModuleFederationPlugin({
      name: 'physicalAi',
      filename: 'remoteEntry.js',
      runtime: false,
      exposes: {
        './extensions': './src/extensions',
      },
      shared: {
        react: { singleton: true, requiredVersion: deps['react'] },
        'react-dom': { singleton: true, requiredVersion: deps['react-dom'] },
        'react-router-dom': { singleton: true, requiredVersion: deps['react-router-dom'] },
        '@patternfly/react-core': { singleton: true, requiredVersion: deps['@patternfly/react-core'] },
      },
    }),
  ],
};
```

`frontend/eslint.config.mjs`:

```javascript
import js from '@eslint/js';
import tseslint from 'typescript-eslint';

export default tseslint.config(
  js.configs.recommended,
  ...tseslint.configs.recommended,
  {
    files: ['src/**/*.{ts,tsx}', 'test/**/*.{ts,tsx}'],
    languageOptions: {
      parserOptions: {
        projectService: true,
        tsconfigRootDir: import.meta.dirname,
      },
    },
  },
  {
    ignores: ['dist/', 'node_modules/', 'webpack.config.js', 'eslint.config.mjs'],
  },
);
```

- [ ] **Step 4: Create frontend source files**

`frontend/src/index.ts`:

```typescript
import('./bootstrap');
```

`frontend/src/bootstrap.tsx`:

```typescript
export {};
```

`frontend/src/PhysicalAiStudioNavIcon.ts`:

```typescript
import { createIcon } from '@patternfly/react-icons/dist/esm/createIcon';

const PhysicalAiStudioNavIcon = createIcon({
  name: 'PhysicalAiStudioNavIcon',
  width: 32,
  height: 32,
  svgPath:
    'M4.60352,13h8.89648c.82715,0,1.5-.67285,1.5-1.5V2.60352c0-.50781-.30371-.96143-.77246-1.15527-.4668-.19336-1.00293-.08691-1.36133.27148L3.71875,10.86719c-.3584.35938-.46387.89404-.26953,1.3623s.64746.77051,1.1543.77051ZM13,4.41406v6.58594h-6.58594l6.58594-6.58594Z M28.5,16H3.5c-.82715,0-1.5.67285-1.5,1.5v11c0,.82715.67285,1.5,1.5,1.5h5.5c.55273,0,1-.44727,1-1,0-3.30859,2.69141-6,6-6s6,2.69141,6,6c0,.55273.44727,1,1,1h5.5c.82715,0,1.5-.67285,1.5-1.5v-11c0-.82715-.67285-1.5-1.5-1.5ZM28,28h-4.0625c-.49316-3.94043-3.86523-7-7.9375-7s-7.44434,3.05957-7.9375,7h-4.0625v-10h24v10Z M19.5,13h8c.82715,0,1.5-.67285,1.5-1.5V3.5c0-.82715-.67285-1.5-1.5-1.5h-8c-.82715,0-1.5.67285-1.5,1.5v8c0,.82715.67285,1.5,1.5,1.5ZM20,4h7v7h-7v-7Z',
  xOffset: 0,
  yOffset: 0,
});

export default PhysicalAiStudioNavIcon;
```

`frontend/src/extensions.ts`:

```typescript
const PHYSICAL_AI_STUDIO = 'physical-ai-studio';

const extensions = [
  {
    type: 'app.navigation/section',
    properties: {
      id: PHYSICAL_AI_STUDIO,
      title: 'Physical AI studio',
      group: '4_physical_ai_studio',
      iconRef: () => import('./PhysicalAiStudioNavIcon'),
    },
  },
  {
    type: 'app.navigation/href',
    properties: {
      id: 'robotics-playground',
      title: 'Robotics Playground',
      href: '/physicalAiStudio/roboticsPlayground',
      section: PHYSICAL_AI_STUDIO,
      path: '/physicalAiStudio/roboticsPlayground/*',
      label: 'Experimental',
    },
  },
  {
    type: 'app.route',
    properties: {
      path: '/physicalAiStudio/roboticsPlayground/*',
      component: () => import('./RoboticsPlayground'),
    },
  },
];

export default extensions;
```

`frontend/src/RoboticsPlayground.tsx`:

```tsx
import React from 'react';
import {
  EmptyState,
  EmptyStateBody,
  PageSection,
} from '@patternfly/react-core';
import { RobotIcon } from '@patternfly/react-icons';

const RoboticsPlayground: React.FC = () => (
  <PageSection>
    <EmptyState titleText="Robotics Playground" headingLevel="h1" icon={RobotIcon}>
      <EmptyStateBody>
        Experiment with robot policy models in a simulated environment.
        This feature is under development.
      </EmptyStateBody>
    </EmptyState>
  </PageSection>
);

export default RoboticsPlayground;
```

`frontend/src/App.tsx`:

```tsx
import React from 'react';
import { BrowserRouter, Routes, Route } from 'react-router-dom';
import { Page } from '@patternfly/react-core';
import RoboticsPlayground from './RoboticsPlayground';

const App: React.FC = () => (
  <BrowserRouter>
    <Page>
      <Routes>
        <Route path="/*" element={<RoboticsPlayground />} />
      </Routes>
    </Page>
  </BrowserRouter>
);

export default App;
```

- [ ] **Step 5: Write the failing frontend test**

`frontend/test/App.test.tsx`:

```tsx
import { describe, it, expect } from 'vitest';
import { render, screen } from '@testing-library/react';
import App from '../src/App';

describe('App', () => {
  it('renders the Robotics Playground heading', () => {
    render(<App />);
    expect(screen.getByText('Robotics Playground')).toBeDefined();
  });

  it('renders the description text', () => {
    render(<App />);
    expect(
      screen.getByText(/Experiment with robot policy models/)
    ).toBeDefined();
  });
});
```

- [ ] **Step 6: Install dependencies and run tests**

```bash
cd frontend && npm install
npm run typecheck
npm run lint
npm test
```

Expected: typecheck passes, lint passes, both tests pass.

- [ ] **Step 7: Verify webpack build produces remoteEntry.js**

```bash
cd frontend && npm run build
ls dist/remoteEntry.js
```

Expected: file exists.

- [ ] **Step 8: Create partial Makefile with frontend targets**

`Makefile`:

```makefile
.PHONY: dev-frontend test-frontend lint-frontend build-frontend

## Start frontend dev server
dev-frontend:
 cd frontend && npm run dev

## Run frontend tests
test-frontend:
 cd frontend && npm test

## Lint frontend code
lint-frontend:
 cd frontend && npm run lint && npm run typecheck
```

- [ ] **Step 9: Commit**

```bash
git add .
git commit -m "feat: initialize repository with frontend scaffold

Migrate React/PatternFly/Module Federation frontend from
physical-ai-platform-demo. Add ESLint, Vitest, and TypeScript
type checking.

Assisted-By: Claude <noreply@anthropic.com>"
```

---

### Task 2: Backend Scaffold

**Files:**

- Create: `backend/pyproject.toml`
- Create: `backend/src/robotics_playground/__init__.py`, `backend/src/robotics_playground/main.py`, `backend/src/robotics_playground/config.py`
- Create: `backend/tests/__init__.py`, `backend/tests/test_health.py`
- Modify: `Makefile` (add backend targets)

**Interfaces:**

- Produces: `backend/` directory with a runnable FastAPI app. `GET /api/health` returns `{"status": "ok"}`. `GET /api/models?type=robotics` returns a hardcoded list. These endpoints will be consumed by the frontend in Phase 1 and by CI health checks.
  - `GET /api/health` → `{"status": "ok"}`
  - `GET /api/models?type=robotics` → `{"models": [{"id": "dreamzero-v1", "name": "DreamZero", "type": "robotics"}]}`

- [ ] **Step 1: Create pyproject.toml**

`backend/pyproject.toml`:

```toml
[project]
name = "robotics-playground"
version = "0.0.1"
description = "Robotics Playground backend — orchestration proxy for robot policy models"
requires-python = ">=3.12"
license = "Apache-2.0"
dependencies = [
    "fastapi>=0.115.0",
    "uvicorn[standard]>=0.34.0",
    "pydantic-settings>=2.7.0",
]

[project.optional-dependencies]
dev = [
    "pytest>=8.3.0",
    "httpx>=0.28.0",
    "ruff>=0.9.0",
]

[tool.ruff]
target-version = "py312"
line-length = 100
src = ["src"]

[tool.ruff.lint]
select = ["E", "F", "W", "I", "UP", "B", "SIM", "RUF"]

[tool.pytest.ini_options]
testpaths = ["tests"]
pythonpath = ["src"]
```

- [ ] **Step 2: Write the failing test**

`backend/tests/__init__.py`: empty file.

`backend/tests/test_health.py`:

```python
from fastapi.testclient import TestClient

from robotics_playground.main import app


def test_health_returns_ok():
    client = TestClient(app)
    response = client.get("/api/health")
    assert response.status_code == 200
    assert response.json() == {"status": "ok"}


def test_models_returns_list():
    client = TestClient(app)
    response = client.get("/api/models", params={"type": "robotics"})
    assert response.status_code == 200
    data = response.json()
    assert "models" in data
    assert len(data["models"]) >= 1
    assert data["models"][0]["id"] == "dreamzero-v1"
```

- [ ] **Step 3: Run test to verify it fails**

```bash
cd backend && pip install -e ".[dev]" && pytest -v
```

Expected: FAIL — `ModuleNotFoundError: No module named 'robotics_playground'`

- [ ] **Step 4: Write the implementation**

`backend/src/robotics_playground/__init__.py`: empty file.

`backend/src/robotics_playground/config.py`:

```python
from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    host: str = "0.0.0.0"
    port: int = 8000
    log_level: str = "info"


settings = Settings()
```

`backend/src/robotics_playground/main.py`:

```python
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
```

- [ ] **Step 5: Run tests to verify they pass**

```bash
cd backend && pytest -v
```

Expected: 2 passed.

- [ ] **Step 6: Run linting**

```bash
cd backend && ruff check src/ tests/ && ruff format --check src/ tests/
```

Expected: no errors, no formatting issues. If formatting issues, run `ruff format src/ tests/` and re-check.

- [ ] **Step 7: Add backend targets to Makefile**

Append to `Makefile`:

```makefile
.PHONY: dev-backend test-backend lint-backend

## Start backend dev server
dev-backend:
 cd backend && uvicorn robotics_playground.main:app --reload --host 0.0.0.0 --port 8000

## Run backend tests
test-backend:
 cd backend && pytest -v

## Lint backend code
lint-backend:
 cd backend && ruff check src/ tests/ && ruff format --check src/ tests/
```

- [ ] **Step 8: Verify Makefile targets work**

```bash
make lint-backend
make test-backend
```

Expected: both pass.

- [ ] **Step 9: Commit**

```bash
git add backend/ Makefile
git commit -m "feat: add Python/FastAPI backend scaffold

Health endpoint at /api/health, model listing at /api/models.
Ruff for linting, Pytest for testing.

Assisted-By: Claude <noreply@anthropic.com>"
```

---

### Task 3: Container Builds + Podman Compose

**Files:**

- Create: `frontend/Containerfile`, `frontend/nginx.conf`
- Create: `backend/Containerfile`
- Create: `deploy/compose.yaml`
- Modify: `Makefile` (add build, compose targets)

**Interfaces:**

- Consumes: `frontend/` (Task 1 — npm build producing `dist/`), `backend/` (Task 2 — pip-installable Python package)
- Produces: Two container images buildable with `podman build`. `deploy/compose.yaml` runnable with `podman compose up`. Frontend serves on `:8080`, proxies `/api/*` to backend on `:8000`.

- [ ] **Step 1: Create frontend nginx config**

`frontend/nginx.conf`:

```nginx
worker_processes auto;
error_log /dev/stderr warn;
pid /tmp/nginx.pid;

events {
    worker_connections 1024;
}

http {
    include /etc/nginx/mime.types;
    default_type application/octet-stream;
    access_log /dev/stdout;

    server {
        listen 8080;
        root /opt/app-root/src;
        index index.html;

        location /api/ {
            proxy_pass http://backend:8000;
            proxy_set_header Host $host;
            proxy_set_header X-Real-IP $remote_addr;
        }

        location /ws/ {
            proxy_pass http://backend:8000;
            proxy_http_version 1.1;
            proxy_set_header Upgrade $http_upgrade;
            proxy_set_header Connection "upgrade";
            proxy_set_header Host $host;
        }

        location / {
            try_files $uri $uri/ /remoteEntry.js;
        }
    }
}
```

- [ ] **Step 2: Create frontend Containerfile**

`frontend/Containerfile`:

```dockerfile
FROM docker.io/library/node:22-slim AS builder

WORKDIR /build
COPY package.json package-lock.json* ./
RUN npm ci
COPY tsconfig.json webpack.config.js ./
COPY src/ src/
RUN npm run build

FROM registry.access.redhat.com/hi/nginx:latest

COPY --from=builder /build/dist/ /opt/app-root/src/
COPY nginx.conf /etc/nginx/nginx.conf

EXPOSE 8080
```

- [ ] **Step 3: Create backend Containerfile**

`backend/Containerfile`:

```dockerfile
FROM registry.access.redhat.com/hi/python:3.14-builder AS builder

WORKDIR /build
COPY pyproject.toml ./
COPY src/ src/
RUN pip install --no-cache-dir --prefix=/install .

FROM registry.access.redhat.com/hi/python:3.14

COPY --from=builder /install /usr/local
COPY src/ /app/src/

WORKDIR /app
EXPOSE 8000

CMD ["uvicorn", "robotics_playground.main:app", "--host", "0.0.0.0", "--port", "8000"]
```

- [ ] **Step 4: Build both container images**

```bash
cd frontend && podman build -t robotics-playground-ui:local -f Containerfile .
cd ../backend && podman build -t robotics-playground:local -f Containerfile .
```

Expected: both builds succeed. If the Hummingbird base images fail (e.g., `hi/python:3.14` path issues), adjust paths in Containerfile and document the issue.

- [ ] **Step 5: Create Podman Compose file**

`deploy/compose.yaml`:

```yaml
services:
  ui:
    image: robotics-playground-ui:local
    build:
      context: ../frontend
      dockerfile: Containerfile
    ports:
      - "8080:8080"
    depends_on:
      backend:
        condition: service_started

  backend:
    image: robotics-playground:local
    build:
      context: ../backend
      dockerfile: Containerfile
    ports:
      - "8000:8000"
```

- [ ] **Step 6: Add build and compose targets to Makefile**

Append to `Makefile`:

```makefile
IMAGE_UI ?= robotics-playground-ui
IMAGE_BACKEND ?= robotics-playground
TAG ?= local

.PHONY: build build-frontend-image build-backend-image compose-up compose-down

## Build both container images
build: build-frontend-image build-backend-image

## Build frontend container image
build-frontend-image:
 podman build -t $(IMAGE_UI):$(TAG) -f frontend/Containerfile frontend/

## Build backend container image
build-backend-image:
 podman build -t $(IMAGE_BACKEND):$(TAG) -f backend/Containerfile backend/

## Start Podman Compose stack
compose-up:
 podman compose -f deploy/compose.yaml up -d

## Stop Podman Compose stack
compose-down:
 podman compose -f deploy/compose.yaml down
```

- [ ] **Step 7: Start Compose stack and verify**

```bash
make build
make compose-up
sleep 3
curl -s http://localhost:8000/api/health | python3 -c "import sys,json; d=json.load(sys.stdin); assert d=={'status':'ok'}, d; print('OK')"
curl -s http://localhost:8080/remoteEntry.js | head -c 100
make compose-down
```

Expected: health returns `{"status": "ok"}`, remoteEntry.js is served. If `hi/nginx` serves from a different path, adjust `nginx.conf` and `Containerfile`.

- [ ] **Step 8: Commit**

```bash
git add frontend/Containerfile frontend/nginx.conf backend/Containerfile deploy/compose.yaml Makefile
git commit -m "feat: add container builds and Podman Compose

Frontend: node builder → hi/nginx with API proxy config.
Backend: hi/python builder → hi/python distroless.
Compose file deploys both for local integration testing.

Assisted-By: Claude <noreply@anthropic.com>"
```

---

### Task 4: Kustomize Manifests

**Files:**

- Create: `deploy/kustomize/kustomization.yaml`, `deploy/kustomize/ui-deployment.yaml`, `deploy/kustomize/ui-service.yaml`, `deploy/kustomize/backend-deployment.yaml`, `deploy/kustomize/backend-service.yaml`
- Modify: `Makefile` (add validate target)

**Interfaces:**

- Consumes: container images from Task 3
- Produces: `kustomize build deploy/kustomize/` renders valid K8s manifests. `kubeconform` validates them.

- [ ] **Step 1: Create Kustomize manifests**

`deploy/kustomize/ui-deployment.yaml`:

```yaml
apiVersion: apps/v1
kind: Deployment
metadata:
  name: robotics-playground-ui
  labels:
    app.kubernetes.io/name: robotics-playground-ui
    app.kubernetes.io/component: frontend
    app.kubernetes.io/part-of: robotics-playground
spec:
  replicas: 1
  selector:
    matchLabels:
      app.kubernetes.io/name: robotics-playground-ui
  template:
    metadata:
      labels:
        app.kubernetes.io/name: robotics-playground-ui
        app.kubernetes.io/component: frontend
        app.kubernetes.io/part-of: robotics-playground
    spec:
      containers:
        - name: nginx
          image: quay.io/redhat-et/robotics-playground-ui:latest
          ports:
            - name: http
              containerPort: 8080
              protocol: TCP
          readinessProbe:
            httpGet:
              path: /remoteEntry.js
              port: http
            initialDelaySeconds: 2
            periodSeconds: 10
          resources:
            requests:
              cpu: 10m
              memory: 32Mi
            limits:
              memory: 64Mi
```

`deploy/kustomize/ui-service.yaml`:

```yaml
apiVersion: v1
kind: Service
metadata:
  name: robotics-playground-ui
  labels:
    app.kubernetes.io/name: robotics-playground-ui
    app.kubernetes.io/component: frontend
    app.kubernetes.io/part-of: robotics-playground
spec:
  selector:
    app.kubernetes.io/name: robotics-playground-ui
  ports:
    - name: http
      port: 8080
      targetPort: http
      protocol: TCP
```

`deploy/kustomize/backend-deployment.yaml`:

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
```

`deploy/kustomize/backend-service.yaml`:

```yaml
apiVersion: v1
kind: Service
metadata:
  name: backend
  labels:
    app.kubernetes.io/name: robotics-playground-backend
    app.kubernetes.io/component: backend
    app.kubernetes.io/part-of: robotics-playground
spec:
  selector:
    app.kubernetes.io/name: robotics-playground-backend
  ports:
    - name: http
      port: 8000
      targetPort: http
      protocol: TCP
```

Note: the backend Service is named `backend` (not `robotics-playground-backend`) so that the frontend's `nginx.conf` proxy_pass to `http://backend:8000` works without modification in both Compose and K8s.

`deploy/kustomize/kustomization.yaml`:

```yaml
apiVersion: kustomize.config.k8s.io/v1beta1
kind: Kustomization

resources:
  - ui-deployment.yaml
  - ui-service.yaml
  - backend-deployment.yaml
  - backend-service.yaml
```

- [ ] **Step 2: Add validate target to Makefile**

Append to `Makefile`:

```makefile
KUSTOMIZE_BUILD := $(if $(shell command -v kustomize 2>/dev/null),kustomize build,kubectl kustomize)

.PHONY: validate lint test dev

## Validate Kustomize manifests
validate:
 @echo "=== kustomize build ==="
 $(KUSTOMIZE_BUILD) deploy/kustomize/ > /dev/null
 @echo "=== kubeconform ==="
 $(KUSTOMIZE_BUILD) deploy/kustomize/ | kubeconform -strict -summary -verbose

## Run all linters
lint: lint-frontend lint-backend

## Run all tests
test: test-frontend test-backend

## Start all dev servers (run in separate terminals)
dev:
 @echo "Run in separate terminals:"
 @echo "  make dev-frontend"
 @echo "  make dev-backend"
```

- [ ] **Step 3: Render and validate**

```bash
kustomize build deploy/kustomize/
kustomize build deploy/kustomize/ | kubeconform -strict -summary -verbose
```

Expected: renders 4 resources (2 Deployments, 2 Services), kubeconform reports all valid.

- [ ] **Step 4: Run full validation**

```bash
make lint
make test
make validate
```

Expected: all three pass.

- [ ] **Step 5: Commit**

```bash
git add deploy/kustomize/ Makefile
git commit -m "feat: add Kustomize manifests for standalone K8s deployment

Two Deployments (ui + backend) and two Services.
Backend Service named 'backend' to match nginx proxy_pass config.

Assisted-By: Claude <noreply@anthropic.com>"
```

---

### Task 5: GitHub Actions CI

**Files:**

- Create: `.github/workflows/ci.yaml`
- Create: `.github/workflows/containers.yaml`
- Create: `.github/workflows/validate-manifests.yaml`
- Create: `.yamllint.yaml`

**Interfaces:**

- Consumes: all previous tasks (frontend lint/test, backend lint/test, container builds, manifest validation)
- Produces: CI pipelines that run on every PR and push to main. Container images pushed to `quay.io/redhat-et/robotics-playground{,-ui}` on merge to main.

- [ ] **Step 1: Create yamllint config**

`.yamllint.yaml`:

```yaml
extends: default

rules:
  document-start: disable
  line-length:
    max: 200
  truthy:
    check-keys: false
  comments:
    min-spaces-from-content: 1
```

- [ ] **Step 2: Create lint + test workflow**

`.github/workflows/ci.yaml`:

```yaml
name: CI

on:
  pull_request:
    branches: [main]
  push:
    branches: [main]

jobs:
  lint-frontend:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v7
      - uses: actions/setup-node@v6
        with:
          node-version: '22'
          cache: 'npm'
          cache-dependency-path: frontend/package-lock.json
      - run: cd frontend && npm ci
      - run: cd frontend && npm run lint
      - run: cd frontend && npm run typecheck

  test-frontend:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v7
      - uses: actions/setup-node@v6
        with:
          node-version: '22'
          cache: 'npm'
          cache-dependency-path: frontend/package-lock.json
      - run: cd frontend && npm ci
      - run: cd frontend && npm test

  lint-backend:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v7
      - uses: astral-sh/setup-uv@08807647e7069bb48b6ef5acd8ec9567f424441b  # v8.1.0
      - run: cd backend && uv pip install --system -e ".[dev]"
      - run: cd backend && ruff check src/ tests/
      - run: cd backend && ruff format --check src/ tests/

  test-backend:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v7
      - uses: astral-sh/setup-uv@08807647e7069bb48b6ef5acd8ec9567f424441b  # v8.1.0
      - run: cd backend && uv pip install --system -e ".[dev]"
      - run: cd backend && pytest -v

  lint-yaml:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v7
      - uses: astral-sh/setup-uv@08807647e7069bb48b6ef5acd8ec9567f424441b  # v8.1.0
      - run: uvx yamllint -c .yamllint.yaml deploy/
```

- [ ] **Step 3: Create multi-arch container build workflow**

`.github/workflows/containers.yaml`:

```yaml
name: Container Images

on:
  pull_request:
    branches: [main]
  push:
    branches: [main]
    tags: ['v*']

env:
  REGISTRY: quay.io
  IMAGE_UI: quay.io/redhat-et/robotics-playground-ui
  IMAGE_BACKEND: quay.io/redhat-et/robotics-playground

jobs:
  build:
    strategy:
      matrix:
        include:
          - arch: amd64
            runner: ubuntu-latest
          - arch: arm64
            runner: ubuntu-24.04-arm
    runs-on: ${{ matrix.runner }}
    steps:
      - uses: actions/checkout@v7

      - name: Build frontend image
        run: |
          podman build \
            -t ${{ env.IMAGE_UI }}:${{ matrix.arch }}-${{ github.sha }} \
            -f frontend/Containerfile frontend/

      - name: Build backend image
        run: |
          podman build \
            -t ${{ env.IMAGE_BACKEND }}:${{ matrix.arch }}-${{ github.sha }} \
            -f backend/Containerfile backend/

      - name: Login to Quay.io
        if: github.event_name == 'push'
        run: podman login -u ${{ secrets.QUAY_USERNAME }} -p ${{ secrets.QUAY_PASSWORD }} quay.io

      - name: Push per-arch images
        if: github.event_name == 'push'
        run: |
          podman push ${{ env.IMAGE_UI }}:${{ matrix.arch }}-${{ github.sha }}
          podman push ${{ env.IMAGE_BACKEND }}:${{ matrix.arch }}-${{ github.sha }}

      - name: Tag and push release images
        if: startsWith(github.ref, 'refs/tags/v')
        run: |
          TAG=${GITHUB_REF#refs/tags/}
          for img in ${{ env.IMAGE_UI }} ${{ env.IMAGE_BACKEND }}; do
            podman tag ${img}:${{ matrix.arch }}-${{ github.sha }} ${img}:${{ matrix.arch }}-${TAG}
            podman push ${img}:${{ matrix.arch }}-${TAG}
          done

  manifest:
    needs: build
    if: github.event_name == 'push'
    runs-on: ubuntu-latest
    steps:
      - name: Login to Quay.io
        run: podman login -u ${{ secrets.QUAY_USERNAME }} -p ${{ secrets.QUAY_PASSWORD }} quay.io

      - name: Create and push manifest lists (commit sha)
        run: |
          for img in ${{ env.IMAGE_UI }} ${{ env.IMAGE_BACKEND }}; do
            podman manifest create ${img}:${{ github.sha }}
            podman manifest add ${img}:${{ github.sha }} ${img}:amd64-${{ github.sha }}
            podman manifest add ${img}:${{ github.sha }} ${img}:arm64-${{ github.sha }}
            podman manifest push ${img}:${{ github.sha }} docker://${img}:${{ github.sha }}
          done

      - name: Create and push manifest lists (latest)
        if: github.ref == 'refs/heads/main'
        run: |
          for img in ${{ env.IMAGE_UI }} ${{ env.IMAGE_BACKEND }}; do
            podman manifest create ${img}:latest
            podman manifest add ${img}:latest ${img}:amd64-${{ github.sha }}
            podman manifest add ${img}:latest ${img}:arm64-${{ github.sha }}
            podman manifest push ${img}:latest docker://${img}:latest
          done

      - name: Create and push manifest lists (release tag)
        if: startsWith(github.ref, 'refs/tags/v')
        run: |
          TAG=${GITHUB_REF#refs/tags/}
          for img in ${{ env.IMAGE_UI }} ${{ env.IMAGE_BACKEND }}; do
            podman manifest create ${img}:${TAG}
            podman manifest add ${img}:${TAG} ${img}:amd64-${{ github.sha }}
            podman manifest add ${img}:${TAG} ${img}:arm64-${{ github.sha }}
            podman manifest push ${img}:${TAG} docker://${img}:${TAG}
          done
```

- [ ] **Step 4: Create manifest validation workflow**

`.github/workflows/validate-manifests.yaml`:

```yaml
name: Validate Manifests

on:
  pull_request:
    branches: [main]
  push:
    branches: [main]

env:
  KUSTOMIZE_VERSION: '5.6.0'
  KUBECONFORM_VERSION: '0.6.7'

jobs:
  validate:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v7

      - uses: astral-sh/setup-uv@08807647e7069bb48b6ef5acd8ec9567f424441b  # v8.1.0

      - name: Install kustomize
        run: |
          curl -sL "https://github.com/kubernetes-sigs/kustomize/releases/download/kustomize%2Fv${KUSTOMIZE_VERSION}/kustomize_v${KUSTOMIZE_VERSION}_linux_amd64.tar.gz" \
            | tar xz -C /usr/local/bin

      - name: Install kubeconform
        run: |
          curl -sL "https://github.com/yannh/kubeconform/releases/download/v${KUBECONFORM_VERSION}/kubeconform-linux-amd64.tar.gz" \
            | tar xz -C /usr/local/bin

      - name: Lint YAML
        run: uvx yamllint -c .yamllint.yaml deploy/

      - name: Validate manifests
        run: |
          kustomize build deploy/kustomize/ | kubeconform \
            -strict -summary -verbose \
            -kubernetes-version 1.34.0 \
            -schema-location default
```

- [ ] **Step 5: Validate all workflows are syntactically correct**

```bash
uvx yamllint -c .yamllint.yaml .github/workflows/
```

Expected: no errors.

- [ ] **Step 6: Run full verification**

```bash
make lint
make test
make build
make compose-up
sleep 3
curl -s http://localhost:8000/api/health
curl -s http://localhost:8080/remoteEntry.js | head -c 50
make compose-down
make validate
```

Expected: all commands succeed.

- [ ] **Step 7: Commit**

```bash
git add .github/ .yamllint.yaml
git commit -m "ci: add GitHub Actions for lint, test, multi-arch containers, and manifest validation

Three workflows:
- ci.yaml: lint + typecheck + test for frontend and backend
- containers.yaml: multi-arch build on native runners, manifest lists
- validate-manifests.yaml: kustomize + kubeconform

Assisted-By: Claude <noreply@anthropic.com>"
```

- [ ] **Step 8: Push to GitHub**

```bash
git push -u origin main
```

Expected: all three CI workflows trigger and pass (container push will fail without Quay.io secrets configured — this is expected until secrets are set up in the repo settings).
