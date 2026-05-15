import unittest
from unittest.mock import patch

from app.catalog import CatalogItem
from app.config import Settings
from app.catalog_store import PostgresCatalogStore


class _Transaction:
    def __init__(self, conn):
        self.conn = conn

    def __enter__(self):
        self.conn.events.append("transaction:enter")
        return self

    def __exit__(self, exc_type, exc, tb):
        self.conn.events.append("transaction:exit")


class _Connection:
    def __init__(self, rows=None):
        self.calls = []
        self.events = []
        self.rows = rows or []

    def __enter__(self):
        self.events.append("connect:enter")
        return self

    def __exit__(self, exc_type, exc, tb):
        self.events.append("connect:exit")

    def execute(self, sql, params=None):
        self.calls.append((sql, params))
        return self

    def fetchall(self):
        return self.rows

    def transaction(self):
        return _Transaction(self)


def _catalog_item(**payload_overrides):
    payload = {
        "id": "item-1",
        "name": "Кофе-брейк",
        "category": "Питание",
        "unit": "чел",
        "unit_price": 450.0,
        "source_text": "Кофе, чай и выпечка",
        "section": "Кейтеринг",
        "supplier": "ООО Питание",
        "has_vat": "В т.ч. НДС",
        "supplier_inn": "7704856280",
        "supplier_city": "г. Москва",
        "supplier_phone": "+7 000 000-00-00",
        "supplier_email": "sales@example.test",
        "supplier_status": "Активен",
        "city_normalized": "москва",
        "supplier_status_normalized": "активен",
        "service_type": "catering",
        "unit_kind": "person",
        "quantity_kind": "per_guest",
    }
    payload.update(payload_overrides)
    return CatalogItem(id=payload["id"], vector=[0.1, 0.2, 0.3], payload=payload, unit_price=450.0)


class PostgresCatalogStoreReplaceTests(unittest.TestCase):
    def test_replace_catalog_creates_schema_deletes_old_rows_and_inserts_payload_vectors(self):
        conn = _Connection()
        store = PostgresCatalogStore(Settings(database_url="postgresql://test"))

        with (
            patch.object(store, "_connect", return_value=conn),
            patch("app.catalog_store.LMStudioClient", create=True) as lm_client,
        ):
            store.replace_catalog([_catalog_item()])

        lm_client.assert_not_called()
        sql = "\n".join(call[0] for call in conn.calls)
        self.assertIn("CREATE EXTENSION IF NOT EXISTS vector", sql)
        self.assertIn("CREATE TABLE IF NOT EXISTS catalog_suppliers", sql)
        self.assertIn("CREATE TABLE IF NOT EXISTS catalog_price_items", sql)
        self.assertIn("CREATE TABLE IF NOT EXISTS catalog_embeddings", sql)

        delete_index = next(i for i, call in enumerate(conn.calls) if "DELETE FROM catalog_price_items" in call[0])
        supplier_insert_index = next(i for i, call in enumerate(conn.calls) if "INSERT INTO catalog_suppliers" in call[0])
        self.assertLess(delete_index, supplier_insert_index)

        supplier_params = conn.calls[supplier_insert_index][1]
        self.assertEqual(
            supplier_params,
            (
                "7704856280",
                "ООО Питание",
                "7704856280",
                "г. Москва",
                "москва",
                "+7 000 000-00-00",
                "sales@example.test",
                "Активен",
                "активен",
            ),
        )

        embedding_params = next(
            params for sql, params in conn.calls if "INSERT INTO catalog_embeddings" in sql
        )
        self.assertEqual(embedding_params, ("item-1", "[0.1,0.2,0.3]"))

    def test_supplier_id_falls_back_to_normalized_supplier_name(self):
        conn = _Connection()
        store = PostgresCatalogStore(Settings(database_url="postgresql://test"))

        with patch.object(store, "_connect", return_value=conn):
            store.replace_catalog([_catalog_item(supplier_inn="", supplier="  ООО Ромашка  ")])

        supplier_params = next(params for sql, params in conn.calls if "INSERT INTO catalog_suppliers" in sql)
        self.assertEqual(supplier_params[0], "ооо ромашка")


class PostgresCatalogStoreSearchTests(unittest.TestCase):
    def test_search_orders_by_pgvector_distance_and_returns_existing_payload_shape(self):
        rows = [
            {
                "score": 0.24,
                "id": "item-1",
                "name": "Кофе-брейк",
                "category": "Питание",
                "unit": "чел",
                "unit_price": 450.0,
                "source_text": "Кофе, чай и выпечка",
                "section": "Кейтеринг",
                "has_vat": "В т.ч. НДС",
                "service_type": "catering",
                "unit_kind": "person",
                "quantity_kind": "per_guest",
                "supplier": "ООО Питание",
                "supplier_inn": "7704856280",
                "supplier_city": "Москва",
                "supplier_phone": "+7",
                "supplier_email": "sales@example.test",
                "supplier_status": "Активен",
                "city_normalized": "москва",
                "supplier_status_normalized": "активен",
            }
        ]
        conn = _Connection(rows)
        store = PostgresCatalogStore(Settings(database_url="postgresql://test"))

        with patch.object(store, "_connect", return_value=conn):
            results = store.search([0.1, 0.2, 0.3], limit=5)

        search_sql, search_params = conn.calls[-1]
        self.assertIn("embedding <=> %s::vector", search_sql)
        self.assertIn("ORDER BY embedding <=> %s::vector", search_sql)
        self.assertEqual(search_params, ("[0.1,0.2,0.3]", "[0.1,0.2,0.3]", 5))
        self.assertEqual(
            results,
            [
                {
                    "score": 0.24,
                    "payload": {
                        "id": "item-1",
                        "name": "Кофе-брейк",
                        "category": "Питание",
                        "unit": "чел",
                        "unit_price": 450.0,
                        "source_text": "Кофе, чай и выпечка",
                        "section": "Кейтеринг",
                        "supplier": "ООО Питание",
                        "has_vat": "В т.ч. НДС",
                        "supplier_inn": "7704856280",
                        "supplier_city": "Москва",
                        "supplier_phone": "+7",
                        "supplier_email": "sales@example.test",
                        "supplier_status": "Активен",
                        "service_type": "catering",
                        "city_normalized": "москва",
                        "supplier_status_normalized": "активен",
                        "unit_kind": "person",
                        "quantity_kind": "per_guest",
                    },
                }
            ],
        )

    def test_search_applies_service_city_and_active_filters_in_sql(self):
        conn = _Connection()
        store = PostgresCatalogStore(Settings(database_url="postgresql://test"))

        with patch.object(store, "_connect", return_value=conn):
            store.search(
                [0.1, 0.2, 0.3],
                limit=3,
                filters={"service_type": "catering", "city": "москва", "only_active": True},
            )

        search_sql, search_params = conn.calls[-1]
        self.assertIn("pi.service_type = %s", search_sql)
        self.assertIn("s.city_normalized = %s", search_sql)
        self.assertIn("s.status_normalized = %s", search_sql)
        self.assertEqual(
            search_params,
            ("[0.1,0.2,0.3]", "catering", "москва", "активен", "[0.1,0.2,0.3]", 3),
        )


if __name__ == "__main__":
    unittest.main()
