# Pgvector Catalog Search Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Move catalog storage/search from Qdrant payloads to PostgreSQL + pgvector, add supplier-grouped catalog access, and make brief output present shortlisted contractors instead of final choices.

**Architecture:** PostgreSQL is the source of truth for catalog rows and suppliers. pgvector stores the ready-made vectors from `prices.csv`; query embeddings are still generated only for user queries. Search retrieves vector candidates, enriches them with SQL fields, filters/reranks, and brief generation groups candidates by service need and supplier.

**Tech Stack:** FastAPI, psycopg 3, PostgreSQL pgvector extension, React/Vite, unittest.

---

## Files And Responsibilities

- `backend/app/catalog_store.py`: new PostgreSQL catalog store; owns schema creation, full catalog replacement, pgvector search, supplier listing, and supplier details.
- `backend/app/ingest.py`: replace Qdrant upload with PostgreSQL catalog replacement.
- `backend/app/search.py`: use `PostgresCatalogStore`; keep query embedding via `LMStudioClient`.
- `backend/app/main.py`: expose supplier catalog endpoints for the Catalog tab.
- `backend/app/config.py`: remove Qdrant-specific settings after backend no longer imports Qdrant.
- `backend/pyproject.toml`: replace `qdrant-client` dependency with no extra vector dependency; use raw SQL casts for pgvector.
- `docker-compose.yml`, `Makefile`, `.env.example`, `README.md`: run PostgreSQL with pgvector and update local commands/text away from Qdrant.
- `backend/app/brief.py`, `backend/app/prompts.py`: present candidates as shortlists and avoid final-choice language.
- `frontend/src/App.jsx`, `frontend/src/styles.css`: add real Catalog view grouped by suppliers.
- Tests under `backend/tests/`: add focused tests for catalog store SQL behavior with fake connections, API endpoints, and brief/search behavior.

---

## Task 1: PostgreSQL pgvector Store And Search Migration

**Files:**
- Create: `backend/app/catalog_store.py`
- Modify: `backend/app/ingest.py`
- Modify: `backend/app/search.py`
- Modify: `backend/app/config.py`
- Modify: `backend/pyproject.toml`
- Modify: `docker-compose.yml`
- Modify: `Makefile`
- Modify: `.env.example`
- Modify: `README.md`
- Modify tests: `backend/tests/test_ingest.py`, `backend/tests/test_search.py`
- Create tests: `backend/tests/test_catalog_store.py`
- Delete/retire tests as needed: `backend/tests/test_vector_store.py`

Steps:

- [ ] Write failing tests for `PostgresCatalogStore.replace_catalog()`:
  - It calls `CREATE EXTENSION IF NOT EXISTS vector`.
  - It creates supplier, price item, and embedding tables.
  - It deletes old catalog rows before inserting new rows.
  - It inserts supplier fields from `CatalogItem.payload`.
  - It inserts vectors using pgvector literal strings from the existing `CatalogItem.vector`.
  - It never calls an embedding client.

- [ ] Write failing tests for `PostgresCatalogStore.search()`:
  - It orders by `embedding <=> %s::vector`.
  - It returns payload fields compatible with existing search/brief code.
  - It applies `service_type`, normalized `city`, and `only_active` filters in SQL.

- [ ] Implement `backend/app/catalog_store.py`:
  - `PostgresCatalogStore(settings: Settings | None = None)`.
  - `_connect()` matching `AuthStore` style with `psycopg.connect(settings.database_url, autocommit=True, row_factory=dict_row)`.
  - `ensure_schema()` creates pgvector extension and tables:
    - `catalog_suppliers(id TEXT PRIMARY KEY, name TEXT NOT NULL, inn TEXT, city TEXT, city_normalized TEXT, phone TEXT, email TEXT, status TEXT, status_normalized TEXT)`.
    - `catalog_price_items(id TEXT PRIMARY KEY, supplier_id TEXT REFERENCES catalog_suppliers(id) ON DELETE SET NULL, name TEXT, category TEXT, unit TEXT, unit_price DOUBLE PRECISION NOT NULL DEFAULT 0, source_text TEXT, created_at TEXT, section TEXT, has_vat TEXT, service_type TEXT, unit_kind TEXT, quantity_kind TEXT)`.
    - `catalog_embeddings(item_id TEXT PRIMARY KEY REFERENCES catalog_price_items(id) ON DELETE CASCADE, embedding vector NOT NULL)`.
  - `replace_catalog(items: list[CatalogItem]) -> None` uses a transaction, `DELETE FROM catalog_price_items`, then upserts suppliers, price items, and embeddings.
  - `search(query_vector: list[float], limit: int = 10, filters: dict[str, Any] | None = None) -> list[dict[str, Any]]`.
  - Vector literal helper returns strings like `[0.1,0.2,0.3]`.
  - Supplier id helper uses `supplier_inn` when present, else normalized supplier name, else `unknown`.

- [ ] Update ingest:
  - Keep parsing ready-made vectors from `prices.csv`.
  - Change status stage/message from Qdrant upload to PostgreSQL/pgvector.
  - Call `PostgresCatalogStore(settings).replace_catalog(items)`.

- [ ] Update search:
  - Import `PostgresCatalogStore`.
  - Keep `self.lm.embed([query])[0]` only for user query vectors.
  - Keep existing rerank behavior.

- [ ] Remove Qdrant backend dependency:
  - Remove `qdrant-client` from `backend/pyproject.toml`.
  - Keep `backend/app/vector_store.py` only if tests still reference it; otherwise remove it and its tests.
  - Remove Qdrant settings from `Settings` when no longer imported.

- [ ] Update local runtime:
  - Use `pgvector/pgvector:pg16` for the postgres service in `docker-compose.yml`.
  - Remove Qdrant service and volume.
  - Update Makefile `dev`, `help`, `check-services`, and variables away from Qdrant.
  - Update `.env.example` and README mentions of Qdrant to PostgreSQL/pgvector.

- [ ] Run targeted tests:
  - `UV_CACHE_DIR=../.uv-cache uv run python -m unittest tests.test_catalog_store tests.test_ingest tests.test_search`

---

## Task 2: Supplier Catalog API And Frontend Tab

**Files:**
- Modify: `backend/app/catalog_store.py`
- Modify: `backend/app/main.py`
- Modify tests: `backend/tests/test_api.py`, `backend/tests/test_catalog_store.py`
- Modify: `frontend/src/App.jsx`
- Modify: `frontend/src/styles.css`

Steps:

- [ ] Add store methods and tests:
  - `list_suppliers(limit=50, query=None)` returns grouped supplier rows with `item_count`, `service_types`, `min_price`, `city`, `status`.
  - `get_supplier(supplier_id)` returns supplier metadata plus all `items` for that supplier sorted by `service_type`, `category`, `name`.

- [ ] Add FastAPI endpoints:
  - `GET /api/catalog/suppliers?limit=50&query=...`
  - `GET /api/catalog/suppliers/{supplier_id}`
  - Both require auth and loaded catalog.

- [ ] Add frontend Catalog view:
  - Sidebar Catalog button switches `view` to `"catalog"`.
  - Catalog view loads `/api/catalog/suppliers`.
  - Supplier rows are grouped cards/list items with name, city, status, count, service type chips, and min price.
  - Clicking a supplier opens a details pane with all services/items.
  - Keep UI compact and operational; no marketing page.

- [ ] Run targeted tests:
  - `UV_CACHE_DIR=../.uv-cache uv run python -m unittest tests.test_api tests.test_catalog_store`
  - `npm --prefix frontend test` if a frontend test target exists; otherwise `npm --prefix frontend run build`.

---

## Task 3: Brief Shortlists Instead Of Final Choices

**Files:**
- Modify: `backend/app/brief.py`
- Modify: `backend/app/prompts.py`
- Modify tests: `backend/tests/test_brief_agent.py`, `backend/tests/test_budget.py` if needed

Steps:

- [ ] Write failing tests:
  - Brief search stores several candidate items per needed service.
  - Default answer groups candidates by service need and supplier.
  - Budget lines are not treated as final selected positions unless the user explicitly selected items.
  - Text says candidates/shortlist, not final recommendation.

- [ ] Update brief workflow:
  - `search_catalog_for_services()` should request at least 5 candidates per needed service.
  - `default_answer()` should render “Короткий список подрядчиков” grouped by service label and supplier.
  - Budget estimate should be framed as orientation only or omitted when there are no selected items.
  - Keep `selected_item_ids` unchanged unless user explicitly selects.

- [ ] Update prompts:
  - Replace “итоговый бриф” final-choice language with shortlist language.
  - Reiterate that manager chooses final contractors.

- [ ] Run targeted tests:
  - `UV_CACHE_DIR=../.uv-cache uv run python -m unittest tests.test_brief_agent tests.test_budget`

---

## Final Verification

- [ ] Run all backend tests from `backend/`:
  - `UV_CACHE_DIR=../.uv-cache uv run python -m unittest discover`
- [ ] Run frontend build:
  - `npm --prefix frontend run build`
- [ ] Run `git status --short` and summarize changed files.
- [ ] Dispatch final code review subagent for the whole worktree.
