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
- Always use `make` targets for building, running, and deploying — never run `podman build`, `podman run`, or `podman compose` directly
- `deploy/compose.yaml` must not contain `build:` directives — images are built separately via `make build` and referenced by tag only

## Git Workflow

- Never push directly to `main` — always use feature branches + PRs
- **One PR per logical change** — don't stack multiple commits on one branch across separate PRs. After a PR is merged, create a new branch from `origin/main` for the next change
- Before creating a PR, always `git fetch origin main && git rebase origin/main` to avoid merge conflicts
- After a PR is merged, do not reuse the old branch — `git checkout -b <new-branch> origin/main`
- Images are built and pushed from `main` only — never from feature branches. Wait for PRs to merge and CI to build before deploying

## Development

- `make dev` — start frontend (webpack dev server :9200) + backend (uvicorn :8000)
- `make test` — run all tests (vitest + pytest)
- `make lint` — run all linters (eslint + ruff + yamllint)
- `make build` — build container images with Podman
- `make compose-up` / `make compose-down` — Podman Compose stack
- `make run` / `make stop` — run containers directly (without compose)
- `make validate` — validate Kustomize manifests with kubeconform
