.PHONY: help up down logs test typecheck lint fmt ingest index search ask annotate ui eval \
	eval-expand sync prod-up prod-down prod-logs prod-build

# Allow `make search Q='...'` / `make ask Q='...'`
Q ?=

help:
	@echo "maayan — make targets:"
	@echo "  sync       Install deps (uv sync). Use 'uv sync --extra ml' for embeddings."
	@echo "  up/down    Start/stop local Qdrant (docker compose)."
	@echo "  logs       Tail Qdrant logs."
	@echo "  test       Run pytest (network/models mocked)."
	@echo "  typecheck  Run mypy --strict."
	@echo "  lint/fmt   Run ruff check / ruff format."
	@echo "  ingest     Pull + chunk corpus into SQLite.        (Prompt 1)"
	@echo "  index      Embed + upsert chunks into Qdrant.      (Prompt 2)"
	@echo "  search     Hybrid retrieval. Usage: make search Q='...'   (Prompt 3)"
	@echo "  ask        Grounded, cited answer. Usage: make ask Q='...' (Prompt 4)"
	@echo "  annotate   Add an expert annotation.               (Prompt 5)"
	@echo "  ui         Run the local FastAPI chat + capture UI. (Prompt 6)"
	@echo "  eval       Score retrieval vs gold set (hit@k/MRR). (Prompt 7)"
	@echo "             Add ARGS='--compare' for a variant table."
	@echo "  eval-expand  Compare retrieval with/without query expansion. (Prompt 31)"
	@echo "               Add ARGS='--crosstext' for the cross-text gold set."
	@echo "  prod-up    Build + start the production stack (docker-compose.prod.yml)."
	@echo "  prod-down  Stop the production stack (volumes persist)."
	@echo "  prod-logs  Tail production app + qdrant logs."
	@echo "  prod-build Build the production image only."

sync:
	uv sync

up:
	docker compose up -d

down:
	docker compose down

logs:
	docker compose logs -f qdrant

test:
	uv run pytest

typecheck:
	uv run mypy maayan

lint:
	uv run ruff check maayan tests

fmt:
	uv run ruff format maayan tests

ingest:
	uv run maayan ingest --all

index:
	uv run maayan index

search:
	uv run maayan search "$(Q)"

ask:
	uv run maayan ask "$(Q)"

annotate:
	uv run maayan annotate $(ARGS)

ui:
	uv run maayan ui

eval:
	uv run maayan eval $(ARGS)

eval-expand:
	uv run maayan eval-expand $(ARGS)

# --- production (cloud) -----------------------------------------------------
prod-up:
	docker compose -f docker-compose.prod.yml up -d --build

prod-down:
	docker compose -f docker-compose.prod.yml down

prod-logs:
	docker compose -f docker-compose.prod.yml logs -f

prod-build:
	docker compose -f docker-compose.prod.yml build
