from __future__ import annotations

import re
from threading import Lock
from typing import Any
from typing import ClassVar

from .catalog import CatalogItem
from .config import Settings, get_settings
from .errors import DependencyUnavailableError


def _vector_literal(vector: list[float]) -> str:
    return "[" + ",".join(str(float(value)) for value in vector) + "]"


def _supplier_id(payload: dict[str, Any]) -> str:
    inn = str(payload.get("supplier_inn") or "").strip()
    if inn:
        return inn
    name = str(payload.get("supplier") or "").strip().lower()
    normalized_name = re.sub(r"\s+", " ", name)
    slug = re.sub(r"[^0-9a-zа-яё_-]+", "-", normalized_name)
    slug = re.sub(r"-+", "-", slug).strip("-")
    return slug or "unknown"


class PostgresCatalogStore:
    _schema_lock: ClassVar[Lock] = Lock()
    _schema_ready_databases: ClassVar[set[str]] = set()

    def __init__(self, settings: Settings | None = None):
        self.settings = settings or get_settings()

    def _connect(self):
        try:
            import psycopg
            from psycopg.rows import dict_row
        except ModuleNotFoundError as exc:
            raise DependencyUnavailableError("PostgreSQL catalog driver is not installed") from exc
        return psycopg.connect(
            self.settings.database_url,
            autocommit=True,
            row_factory=dict_row,
        )

    def ensure_schema(self) -> None:
        database_url = self.settings.database_url
        if database_url in self._schema_ready_databases:
            return
        with self._schema_lock:
            if database_url in self._schema_ready_databases:
                return
            with self._connect() as conn:
                conn.execute("CREATE EXTENSION IF NOT EXISTS vector")
                conn.execute(
                    """
                    CREATE TABLE IF NOT EXISTS catalog_suppliers (
                        id TEXT PRIMARY KEY,
                        name TEXT NOT NULL,
                        inn TEXT,
                        city TEXT,
                        city_normalized TEXT,
                        phone TEXT,
                        email TEXT,
                        status TEXT,
                        status_normalized TEXT
                    )
                    """
                )
                conn.execute(
                    """
                    CREATE TABLE IF NOT EXISTS catalog_price_items (
                        id TEXT PRIMARY KEY,
                        supplier_id TEXT REFERENCES catalog_suppliers(id) ON DELETE SET NULL,
                        name TEXT,
                        category TEXT,
                        unit TEXT,
                        unit_price DOUBLE PRECISION NOT NULL DEFAULT 0,
                        source_text TEXT,
                        created_at TEXT,
                        section TEXT,
                        has_vat TEXT,
                        service_type TEXT,
                        unit_kind TEXT,
                        quantity_kind TEXT
                    )
                    """
                )
                conn.execute(
                    """
                    CREATE TABLE IF NOT EXISTS catalog_embeddings (
                        item_id TEXT PRIMARY KEY REFERENCES catalog_price_items(id) ON DELETE CASCADE,
                        embedding vector NOT NULL
                    )
                    """
                )
            self._schema_ready_databases.add(database_url)

    def replace_catalog(self, items: list[CatalogItem]) -> None:
        self.ensure_schema()
        try:
            with self._connect() as conn:
                with conn.transaction():
                    conn.execute("DELETE FROM catalog_price_items")
                    conn.execute("DELETE FROM catalog_suppliers")
                    if not items:
                        conn.execute("DROP INDEX IF EXISTS catalog_embeddings_embedding_hnsw_idx")
                        return

                    dimension = len(items[0].vector)
                    conn.execute("DROP INDEX IF EXISTS catalog_embeddings_embedding_hnsw_idx")
                    conn.execute(
                        "ALTER TABLE catalog_embeddings "
                        f"ALTER COLUMN embedding TYPE vector({dimension}) "
                        f"USING embedding::vector({dimension})"
                    )

                    supplier_params: dict[str, tuple[Any, ...]] = {}
                    item_params: list[tuple[Any, ...]] = []
                    embedding_params: list[tuple[Any, ...]] = []
                    for item in items:
                        payload = item.payload
                        supplier_id = _supplier_id(payload)
                        supplier_params[supplier_id] = _supplier_params(supplier_id, payload)
                        item_params.append(_item_params(item, supplier_id))
                        embedding_params.append((item.id, _vector_literal(item.vector)))

                    _executemany(conn, _SUPPLIER_UPSERT_SQL, list(supplier_params.values()))
                    _executemany(conn, _PRICE_ITEM_UPSERT_SQL, item_params)
                    _executemany(conn, _EMBEDDING_UPSERT_SQL, embedding_params)
                    conn.execute(
                        "CREATE INDEX catalog_embeddings_embedding_hnsw_idx "
                        "ON catalog_embeddings USING hnsw (embedding vector_cosine_ops)"
                    )
        except Exception as exc:
            raise DependencyUnavailableError(
                "PostgreSQL недоступен: не удалось заменить каталог в pgvector."
            ) from exc

    def search(
        self,
        query_vector: list[float],
        limit: int = 10,
        filters: dict[str, Any] | None = None,
    ) -> list[dict[str, Any]]:
        self.ensure_schema()
        vector = _vector_literal(query_vector)
        where: list[str] = []
        params: list[Any] = [vector]
        filters = filters or {}
        if filters.get("service_type"):
            where.append("pi.service_type = %s")
            params.append(filters["service_type"])
        if filters.get("city"):
            where.append("s.city_normalized = %s")
            params.append(filters["city"])
        if filters.get("only_active"):
            where.append("s.status_normalized = %s")
            params.append("активен")

        where_sql = f"WHERE {' AND '.join(where)}" if where else ""
        params.extend([vector, limit])
        try:
            with self._connect() as conn:
                rows = conn.execute(
                    f"""
                    SELECT
                        1 - (e.embedding <=> %s::vector) AS score,
                        pi.id,
                        pi.name,
                        pi.category,
                        pi.unit,
                        pi.unit_price,
                        pi.source_text,
                        pi.section,
                        pi.has_vat,
                        pi.service_type,
                        pi.unit_kind,
                        pi.quantity_kind,
                        s.name AS supplier,
                        s.inn AS supplier_inn,
                        s.city AS supplier_city,
                        s.phone AS supplier_phone,
                        s.email AS supplier_email,
                        s.status AS supplier_status,
                        s.city_normalized,
                        s.status_normalized AS supplier_status_normalized
                    FROM catalog_price_items pi
                    JOIN catalog_embeddings e ON e.item_id = pi.id
                    LEFT JOIN catalog_suppliers s ON s.id = pi.supplier_id
                    {where_sql}
                    ORDER BY embedding <=> %s::vector
                    LIMIT %s
                    """,
                    tuple(params),
                ).fetchall()
        except Exception as exc:
            raise DependencyUnavailableError(
                "PostgreSQL недоступен: не удалось выполнить поиск в pgvector."
            ) from exc

        return [{"score": float(row["score"]), "payload": _row_payload(row)} for row in rows]

    def list_suppliers(self, limit: int = 50, query: str | None = None) -> list[dict[str, Any]]:
        where_sql = ""
        params: list[Any] = []
        normalized_query = (query or "").strip()
        if normalized_query:
            term = f"%{normalized_query}%"
            where_sql = "WHERE s.name ILIKE %s OR s.inn ILIKE %s OR s.city ILIKE %s"
            params.extend([term, term, term])
        params.append(limit)

        try:
            self.ensure_schema()
            with self._connect() as conn:
                rows = conn.execute(
                    f"""
                    SELECT
                        s.id,
                        s.name,
                        s.inn,
                        s.city,
                        s.status,
                        COUNT(pi.id) AS item_count,
                        ARRAY_AGG(DISTINCT pi.service_type) AS service_types,
                        MIN(pi.unit_price) AS min_price
                    FROM catalog_suppliers s
                    LEFT JOIN catalog_price_items pi ON pi.supplier_id = s.id
                    {where_sql}
                    GROUP BY s.id, s.name, s.inn, s.city, s.status
                    ORDER BY LOWER(s.name)
                    LIMIT %s
                    """,
                    tuple(params),
                ).fetchall()
        except Exception as exc:
            raise DependencyUnavailableError(
                "PostgreSQL недоступен: не удалось получить список поставщиков."
            ) from exc

        return [_supplier_summary(row) for row in rows]

    def get_supplier(self, supplier_id: str) -> dict[str, Any] | None:
        try:
            self.ensure_schema()
            with self._connect() as conn:
                rows = conn.execute(
                    """
                    SELECT
                        s.id AS supplier_id,
                        s.name AS supplier_name,
                        s.inn AS supplier_inn,
                        s.city AS supplier_city,
                        s.phone AS supplier_phone,
                        s.email AS supplier_email,
                        s.status AS supplier_status,
                        pi.id AS item_id,
                        pi.name AS item_name,
                        pi.category,
                        pi.unit,
                        pi.unit_price,
                        pi.source_text,
                        pi.section,
                        pi.has_vat,
                        pi.service_type,
                        pi.unit_kind,
                        pi.quantity_kind
                    FROM catalog_suppliers s
                    LEFT JOIN catalog_price_items pi ON pi.supplier_id = s.id
                    WHERE s.id = %s
                    ORDER BY pi.service_type, pi.category, pi.name
                    """,
                    (supplier_id,),
                ).fetchall()
        except Exception as exc:
            raise DependencyUnavailableError(
                "PostgreSQL недоступен: не удалось получить поставщика."
            ) from exc

        if not rows:
            return None
        return _supplier_detail(rows)


def _row_payload(row: dict[str, Any]) -> dict[str, Any]:
    return {
        "id": row.get("id"),
        "name": row.get("name"),
        "category": row.get("category"),
        "unit": row.get("unit"),
        "unit_price": row.get("unit_price"),
        "source_text": row.get("source_text"),
        "section": row.get("section"),
        "supplier": row.get("supplier"),
        "has_vat": row.get("has_vat"),
        "supplier_inn": row.get("supplier_inn"),
        "supplier_city": row.get("supplier_city"),
        "supplier_phone": row.get("supplier_phone"),
        "supplier_email": row.get("supplier_email"),
        "supplier_status": row.get("supplier_status"),
        "service_type": row.get("service_type"),
        "city_normalized": row.get("city_normalized"),
        "supplier_status_normalized": row.get("supplier_status_normalized"),
        "unit_kind": row.get("unit_kind"),
        "quantity_kind": row.get("quantity_kind"),
    }


def _supplier_summary(row: dict[str, Any]) -> dict[str, Any]:
    service_types = sorted(
        str(service_type)
        for service_type in row.get("service_types") or []
        if service_type
    )
    min_price = row.get("min_price")
    return {
        "id": row.get("id"),
        "name": row.get("name"),
        "inn": row.get("inn"),
        "city": row.get("city"),
        "status": row.get("status"),
        "item_count": int(row.get("item_count") or 0),
        "service_types": service_types,
        "min_price": float(min_price) if min_price is not None else None,
    }


def _supplier_detail(rows: list[dict[str, Any]]) -> dict[str, Any]:
    first = rows[0]
    items = []
    for row in rows:
        if not row.get("item_id"):
            continue
        items.append(
            {
                "id": row.get("item_id"),
                "name": row.get("item_name"),
                "category": row.get("category"),
                "unit": row.get("unit"),
                "unit_price": row.get("unit_price"),
                "source_text": row.get("source_text"),
                "section": row.get("section"),
                "has_vat": row.get("has_vat"),
                "service_type": row.get("service_type"),
                "unit_kind": row.get("unit_kind"),
                "quantity_kind": row.get("quantity_kind"),
            }
        )
    return {
        "id": first.get("supplier_id"),
        "name": first.get("supplier_name"),
        "inn": first.get("supplier_inn"),
        "city": first.get("supplier_city"),
        "phone": first.get("supplier_phone"),
        "email": first.get("supplier_email"),
        "status": first.get("supplier_status"),
        "items": items,
    }


_SUPPLIER_UPSERT_SQL = """
INSERT INTO catalog_suppliers (
    id, name, inn, city, city_normalized, phone, email, status, status_normalized
)
VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s)
ON CONFLICT (id) DO UPDATE SET
    name = EXCLUDED.name,
    inn = EXCLUDED.inn,
    city = EXCLUDED.city,
    city_normalized = EXCLUDED.city_normalized,
    phone = EXCLUDED.phone,
    email = EXCLUDED.email,
    status = EXCLUDED.status,
    status_normalized = EXCLUDED.status_normalized
"""

_PRICE_ITEM_UPSERT_SQL = """
INSERT INTO catalog_price_items (
    id, supplier_id, name, category, unit, unit_price, source_text,
    created_at, section, has_vat, service_type, unit_kind, quantity_kind
)
VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
ON CONFLICT (id) DO UPDATE SET
    supplier_id = EXCLUDED.supplier_id,
    name = EXCLUDED.name,
    category = EXCLUDED.category,
    unit = EXCLUDED.unit,
    unit_price = EXCLUDED.unit_price,
    source_text = EXCLUDED.source_text,
    created_at = EXCLUDED.created_at,
    section = EXCLUDED.section,
    has_vat = EXCLUDED.has_vat,
    service_type = EXCLUDED.service_type,
    unit_kind = EXCLUDED.unit_kind,
    quantity_kind = EXCLUDED.quantity_kind
"""

_EMBEDDING_UPSERT_SQL = """
INSERT INTO catalog_embeddings (item_id, embedding)
VALUES (%s, %s::vector)
ON CONFLICT (item_id) DO UPDATE SET embedding = EXCLUDED.embedding
"""


def _supplier_params(supplier_id: str, payload: dict[str, Any]) -> tuple[Any, ...]:
    return (
        supplier_id,
        str(payload.get("supplier") or "Unknown"),
        str(payload.get("supplier_inn") or "") or None,
        str(payload.get("supplier_city") or "") or None,
        str(payload.get("city_normalized") or "") or None,
        str(payload.get("supplier_phone") or "") or None,
        str(payload.get("supplier_email") or "") or None,
        str(payload.get("supplier_status") or "") or None,
        str(payload.get("supplier_status_normalized") or "") or None,
    )


def _item_params(item: CatalogItem, supplier_id: str) -> tuple[Any, ...]:
    payload = item.payload
    return (
        item.id,
        supplier_id,
        str(payload.get("name") or ""),
        str(payload.get("category") or "") or None,
        str(payload.get("unit") or "") or None,
        float(payload.get("unit_price") or item.unit_price or 0),
        str(payload.get("source_text") or "") or None,
        str(payload.get("created_at") or "") or None,
        str(payload.get("section") or "") or None,
        str(payload.get("has_vat") or "") or None,
        str(payload.get("service_type") or "") or None,
        str(payload.get("unit_kind") or "") or None,
        str(payload.get("quantity_kind") or "") or None,
    )


def _executemany(conn: Any, sql: str, params_seq: list[tuple[Any, ...]]) -> None:
    if hasattr(conn, "executemany"):
        conn.executemany(sql, params_seq)
        return
    with conn.cursor() as cur:
        cur.executemany(sql, params_seq)
