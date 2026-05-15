SHELL := /bin/sh

.DEFAULT_GOAL := help

-include .env

UV ?= uv
UV_CACHE_DIR ?= .uv-cache
BACKEND_PROJECT := backend
LM_STUDIO_BASE_URL ?= http://localhost:1234/v1
EMBEDDING_BASE_URL ?= $(if $(API_KEY),https://api.vsellm.ru/v1,$(LM_STUDIO_BASE_URL))
CHAT_BASE_URL ?= $(if $(API_KEY),https://api.vsellm.ru/v1,$(LM_STUDIO_BASE_URL))
DATABASE_URL ?= postgresql://argus:argus@127.0.0.1:5432/argus
LOCAL_NO_PROXY ?= localhost,127.0.0.1,::1,0.0.0.0,host.docker.internal
LM_STUDIO_MODELS_URL := $(patsubst %/,%,$(LM_STUDIO_BASE_URL))/models
EMBEDDING_MODELS_URL := $(patsubst %/,%,$(EMBEDDING_BASE_URL))/models
CHAT_MODELS_URL := $(patsubst %/,%,$(CHAT_BASE_URL))/models

.PHONY: help env install install-root install-backend install-frontend db db-down backend frontend seed-admin dev check-services test test-backend test-frontend build clean

help:
	@echo "ARGUS Brief Agent MVP"
	@echo ""
	@echo "Setup:"
	@echo "  make env              Create .env from .env.example if missing"
	@echo "  make install          Install backend and frontend dependencies"
	@echo ""
	@echo "Run:"
	@echo "  make db               Start local PostgreSQL with pgvector"
	@echo "  make backend          Start FastAPI on http://localhost:8000"
	@echo "  make frontend         Start Vite on http://localhost:5173"
	@echo "  make seed-admin       Create local dev admin user"
	@echo "  make dev              Start PostgreSQL/pgvector, backend, and frontend"
	@echo "  make check-services   Check backend, LM Studio, APIs, and PostgreSQL"
	@echo ""
	@echo "Checks:"
	@echo "  make test             Run backend and frontend tests"
	@echo "  make build            Build frontend bundle"
	@echo ""
	@echo "Stop:"
	@echo "  make db-down          Stop PostgreSQL"

env:
	@test -f .env || cp .env.example .env
	@echo ".env is ready"

install: install-root install-backend install-frontend

install-root:
	npm install

install-backend: env
	UV_CACHE_DIR=$(UV_CACHE_DIR) $(UV) sync --project $(BACKEND_PROJECT)

install-frontend:
	npm --prefix frontend install

db:
	docker compose up -d postgres

db-down:
	docker compose down

backend:
	NO_PROXY="$(LOCAL_NO_PROXY),$(NO_PROXY)" no_proxy="$(LOCAL_NO_PROXY),$(no_proxy)" UV_CACHE_DIR=$(UV_CACHE_DIR) $(UV) run --project $(BACKEND_PROJECT) uvicorn app.main:app --app-dir backend --env-file .env --reload --host 0.0.0.0 --port 8000

frontend:
	npm --prefix frontend run dev

seed-admin: env
	@set -a; . ./.env; set +a; NO_PROXY="$(LOCAL_NO_PROXY),$${NO_PROXY}" no_proxy="$(LOCAL_NO_PROXY),$${no_proxy}" PYTHONPATH=backend UV_CACHE_DIR=$(UV_CACHE_DIR) $(UV) run --project $(BACKEND_PROJECT) python -m app.dev_admin

dev: db
	$(MAKE) -j2 backend frontend

check-services:
	@echo "FastAPI:"
	@NO_PROXY="$(LOCAL_NO_PROXY),$(NO_PROXY)" no_proxy="$(LOCAL_NO_PROXY),$(no_proxy)" curl -fsS http://localhost:8000/api/health || true
	@echo ""
	@echo "LM Studio ($(LM_STUDIO_BASE_URL)):"
	@NO_PROXY="$(LOCAL_NO_PROXY),$(NO_PROXY)" no_proxy="$(LOCAL_NO_PROXY),$(no_proxy)" curl -fsS "$(LM_STUDIO_MODELS_URL)" || true
	@echo ""
	@echo "Embedding API ($(EMBEDDING_BASE_URL)):"
	@curl -fsS -H "Authorization: Bearer $(API_KEY)" "$(EMBEDDING_MODELS_URL)" || true
	@echo ""
	@echo "Chat API ($(CHAT_BASE_URL)):"
	@curl -fsS -H "Authorization: Bearer $(if $(CHAT_API_KEY),$(CHAT_API_KEY),$(API_KEY))" "$(CHAT_MODELS_URL)" || true
	@echo ""
	@echo "PostgreSQL ($(DATABASE_URL)):"
	@docker compose ps postgres || true

test: test-backend test-frontend

test-backend:
	UV_CACHE_DIR=$(UV_CACHE_DIR) $(UV) run --project $(BACKEND_PROJECT) python -m unittest discover -s backend/tests -t backend -v

test-frontend:
	npm --prefix frontend test

build:
	npm --prefix frontend run build

clean:
	rm -rf .uv-cache backend/.venv frontend/dist frontend/node_modules
