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
