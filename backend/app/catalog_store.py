from __future__ import annotations

import re
from typing import Any

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
    return normalized_name or "unknown"


class PostgresCatalogStore:
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

    def replace_catalog(self, items: list[CatalogItem]) -> None:
        self.ensure_schema()
        try:
            with self._connect() as conn:
                with conn.transaction():
                    conn.execute("DELETE FROM catalog_price_items")
                    conn.execute("DELETE FROM catalog_suppliers")
                    for item in items:
                        payload = item.payload
                        supplier_id = _supplier_id(payload)
                        conn.execute(
                            """
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
                            """,
                            (
                                supplier_id,
                                str(payload.get("supplier") or "Unknown"),
                                str(payload.get("supplier_inn") or "") or None,
                                str(payload.get("supplier_city") or "") or None,
                                str(payload.get("city_normalized") or "") or None,
                                str(payload.get("supplier_phone") or "") or None,
                                str(payload.get("supplier_email") or "") or None,
                                str(payload.get("supplier_status") or "") or None,
                                str(payload.get("supplier_status_normalized") or "") or None,
                            ),
                        )
                        conn.execute(
                            """
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
                            """,
                            (
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
                            ),
                        )
                        conn.execute(
                            """
                            INSERT INTO catalog_embeddings (item_id, embedding)
                            VALUES (%s, %s::vector)
                            ON CONFLICT (item_id) DO UPDATE SET embedding = EXCLUDED.embedding
                            """,
                            (item.id, _vector_literal(item.vector)),
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
