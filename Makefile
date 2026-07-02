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
	cd backend && uvicorn robotics_playground.main:app --reload --host 0.0.0.0 --port 8000

## Run backend tests
test-backend:
	cd backend && pytest -v

## Lint backend code
lint-backend:
	cd backend && ruff check src/ tests/ && ruff format --check src/ tests/

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
