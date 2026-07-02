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
