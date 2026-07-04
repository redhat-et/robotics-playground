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

.PHONY: dev-backend test-backend lint-backend

## Start backend dev server
dev-backend:
	cd backend && uv run uvicorn robotics_playground.main:app --reload --host 0.0.0.0 --port 8000

## Run backend tests
test-backend:
	cd backend && uv run pytest -v

## Lint backend code
lint-backend:
	cd backend && uv run ruff check src/ tests/ && uv run ruff format --check src/ tests/

IMAGE_UI ?= robotics-playground-ui
IMAGE_BACKEND ?= robotics-playground
TAG ?= local

.PHONY: build build-frontend-image build-backend-image compose-up compose-down run stop

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

NETWORK ?= rp-net

## Run containers directly (without compose)
run: build
	@podman network exists $(NETWORK) 2>/dev/null || podman network create $(NETWORK)
	podman run -d --name backend --network $(NETWORK) \
		-p 8000:8000 -p 9876:9876 -p 9090:9090 \
		$(IMAGE_BACKEND):$(TAG)
	podman run -d --name ui --network $(NETWORK) \
		-p 8080:8080 \
		$(IMAGE_UI):$(TAG)
	@echo "UI: http://localhost:8080  Backend: http://localhost:8000"

## Stop and remove containers
stop:
	-podman stop ui backend 2>/dev/null
	-podman rm ui backend 2>/dev/null

KUSTOMIZE_BUILD := $(if $(shell command -v kustomize 2>/dev/null),kustomize build,$(if $(shell command -v oc 2>/dev/null),oc kustomize,kubectl kustomize))

.PHONY: validate lint test dev

## Validate Kustomize manifests
validate:
	@command -v kustomize >/dev/null 2>&1 || command -v oc >/dev/null 2>&1 || command -v kubectl >/dev/null 2>&1 || \
		{ echo "ERROR: kustomize, oc, or kubectl required but not found"; exit 1; }
	@command -v kubeconform >/dev/null 2>&1 || \
		{ echo "ERROR: kubeconform required but not found (install: go install github.com/yannh/kubeconform/cmd/kubeconform@latest)"; exit 1; }
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
