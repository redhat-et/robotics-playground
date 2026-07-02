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
