import unittest
from unittest.mock import patch

from app.catalog import CatalogItem
from app.config import Settings
from app.catalog_store import PostgresCatalogStore
from app.errors import DependencyUnavailableError


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
        self.batch_calls = []
        self.events = []
        self.rows = rows or []

    def __enter__(self):
        self.events.append("connect:enter")
        return self

    def __exit__(self, exc_type, exc, tb):
        self.events.append("connect:exit")

    def execute(self, sql, params=None):
        self.calls.append((sql, params))
        self.events.append(("execute", sql))
        return self

    def executemany(self, sql, params_seq):
        self.batch_calls.append((sql, list(params_seq)))
        self.events.append(("executemany", sql))
        return self

    def fetchall(self):
        return self.rows

    def transaction(self):
        return _Transaction(self)


def _catalog_item(item_id="item-1", vector=None, **payload_overrides):
    payload = {
        "id": item_id,
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
    return CatalogItem(
        id=payload["id"],
        vector=vector or [0.1, 0.2, 0.3],
        payload=payload,
        unit_price=450.0,
    )


class PostgresCatalogStoreReplaceTests(unittest.TestCase):
    def setUp(self):
        PostgresCatalogStore._schema_ready_databases.clear()

    def test_replace_catalog_creates_schema_deletes_old_rows_and_inserts_payload_vectors(self):
        conn = _Connection()
        store = PostgresCatalogStore(Settings(database_url="postgresql://test"))

        with patch.object(store, "_connect", return_value=conn):
            store.replace_catalog([_catalog_item()])

        sql = "\n".join(call[0] for call in conn.calls)
        self.assertIn("CREATE EXTENSION IF NOT EXISTS vector", sql)
        self.assertIn("CREATE TABLE IF NOT EXISTS catalog_suppliers", sql)
        self.assertIn("CREATE TABLE IF NOT EXISTS catalog_price_items", sql)
        self.assertIn("CREATE TABLE IF NOT EXISTS catalog_embeddings", sql)

        delete_index = next(
            i for i, event in enumerate(conn.events) if event[0] == "execute" and "DELETE FROM catalog_price_items" in event[1]
        )
        supplier_insert_index = next(
            i for i, event in enumerate(conn.events) if event[0] == "executemany" and "INSERT INTO catalog_suppliers" in event[1]
        )
        self.assertLess(delete_index, supplier_insert_index)

        supplier_sql, supplier_batch = conn.batch_calls[0]
        self.assertIn("INSERT INTO catalog_suppliers", supplier_sql)
        supplier_params = supplier_batch[0]
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

        embedding_sql, embedding_batch = conn.batch_calls[2]
        self.assertIn("INSERT INTO catalog_embeddings", embedding_sql)
        embedding_params = embedding_batch[0]
        self.assertEqual(embedding_params, ("item-1", "[0.1,0.2,0.3]"))

    def test_replace_catalog_batches_suppliers_items_and_embeddings(self):
        conn = _Connection()
        store = PostgresCatalogStore(Settings(database_url="postgresql://test"))
        items = [
            _catalog_item(item_id="item-1", supplier_inn="7704856280"),
            _catalog_item(item_id="item-2", supplier_inn="7704856280"),
        ]

        with patch.object(store, "_connect", return_value=conn):
            store.replace_catalog(items)

        self.assertEqual(len(conn.batch_calls), 3)
        self.assertIn("INSERT INTO catalog_suppliers", conn.batch_calls[0][0])
        self.assertIn("INSERT INTO catalog_price_items", conn.batch_calls[1][0])
        self.assertIn("INSERT INTO catalog_embeddings", conn.batch_calls[2][0])
        self.assertEqual(len(conn.batch_calls[0][1]), 1)
        self.assertEqual(len(conn.batch_calls[1][1]), 2)
        self.assertEqual(len(conn.batch_calls[2][1]), 2)

    def test_replace_catalog_recreates_dimension_aware_hnsw_index_after_embedding_insert(self):
        conn = _Connection()
        store = PostgresCatalogStore(Settings(database_url="postgresql://test"))

        with patch.object(store, "_connect", return_value=conn):
            store.replace_catalog([_catalog_item(vector=[0.1, 0.2, 0.3])])

        embedding_batch_index = next(
            i for i, event in enumerate(conn.events) if event[0] == "executemany" and "INSERT INTO catalog_embeddings" in event[1]
        )
        create_index = next(i for i, event in enumerate(conn.events) if "USING hnsw" in event[1])
        self.assertGreater(create_index, embedding_batch_index)
        self.assertIn("TYPE vector(3)", "\n".join(call[0] for call in conn.calls))
        self.assertIn("vector_cosine_ops", conn.events[create_index][1])

    def test_supplier_id_falls_back_to_url_safe_normalized_supplier_name(self):
        conn = _Connection()
        store = PostgresCatalogStore(Settings(database_url="postgresql://test"))

        with patch.object(store, "_connect", return_value=conn):
            store.replace_catalog([_catalog_item(supplier_inn="", supplier="  ООО Ромашка / Север  ")])

        supplier_params = conn.batch_calls[0][1][0]
        self.assertEqual(supplier_params[0], "ооо-ромашка-север")
        self.assertNotIn("/", supplier_params[0])

    def test_supplier_id_keeps_supplier_inn_when_present(self):
        conn = _Connection()
        store = PostgresCatalogStore(Settings(database_url="postgresql://test"))

        with patch.object(store, "_connect", return_value=conn):
            store.replace_catalog([_catalog_item(supplier_inn="7704856280", supplier="ООО / Ромашка")])

        supplier_params = conn.batch_calls[0][1][0]
        self.assertEqual(supplier_params[0], "7704856280")


class PostgresCatalogStoreSearchTests(unittest.TestCase):
    def setUp(self):
        PostgresCatalogStore._schema_ready_databases.clear()

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

    def test_search_ensures_schema_once_per_store_instance(self):
        conn = _Connection()
        store = PostgresCatalogStore(Settings(database_url="postgresql://test"))

        with patch.object(store, "_connect", return_value=conn):
            store.search([0.1, 0.2, 0.3], limit=1)
            store.search([0.1, 0.2, 0.3], limit=1)

        schema_calls = [sql for sql, _ in conn.calls if "CREATE TABLE IF NOT EXISTS catalog_embeddings" in sql]
        self.assertEqual(len(schema_calls), 1)

    def test_search_ensures_schema_once_across_store_instances(self):
        first_conn = _Connection()
        second_conn = _Connection()
        first_store = PostgresCatalogStore(Settings(database_url="postgresql://test"))
        second_store = PostgresCatalogStore(Settings(database_url="postgresql://test"))

        with patch.object(first_store, "_connect", return_value=first_conn):
            first_store.search([0.1, 0.2, 0.3], limit=1)
        with patch.object(second_store, "_connect", return_value=second_conn):
            second_store.search([0.1, 0.2, 0.3], limit=1)

        first_schema_calls = [
            sql for sql, _ in first_conn.calls if "CREATE TABLE IF NOT EXISTS catalog_embeddings" in sql
        ]
        second_schema_calls = [
            sql for sql, _ in second_conn.calls if "CREATE TABLE IF NOT EXISTS catalog_embeddings" in sql
        ]
        self.assertEqual(len(first_schema_calls), 1)
        self.assertEqual(second_schema_calls, [])


class PostgresCatalogStoreSupplierTests(unittest.TestCase):
    def setUp(self):
        PostgresCatalogStore._schema_ready_databases.clear()

    def test_list_suppliers_returns_grouped_supplier_rows_with_sorted_service_types(self):
        rows = [
            {
                "id": "7704856280",
                "name": "ООО Питание",
                "inn": "7704856280",
                "city": "Москва",
                "status": "Активен",
                "item_count": 2,
                "service_types": ["venue", "catering", None],
                "min_price": 450.0,
            }
        ]
        conn = _Connection(rows)
        store = PostgresCatalogStore(Settings(database_url="postgresql://test"))

        with patch.object(store, "_connect", return_value=conn):
            suppliers = store.list_suppliers(limit=25, query="питание")

        supplier_sql, supplier_params = conn.calls[-1]
        self.assertIn("COUNT(pi.id) AS item_count", supplier_sql)
        self.assertIn("MIN(pi.unit_price) AS min_price", supplier_sql)
        self.assertIn("s.name ILIKE %s", supplier_sql)
        self.assertEqual(supplier_params, ("%питание%", "%питание%", "%питание%", 25))
        self.assertEqual(
            suppliers,
            [
                {
                    "id": "7704856280",
                    "name": "ООО Питание",
                    "inn": "7704856280",
                    "city": "Москва",
                    "status": "Активен",
                    "item_count": 2,
                    "service_types": ["catering", "venue"],
                    "min_price": 450.0,
                }
            ],
        )

    def test_get_supplier_returns_metadata_and_items_sorted_by_catalog_fields(self):
        rows = [
            {
                "supplier_id": "7704856280",
                "supplier_name": "ООО Питание",
                "supplier_inn": "7704856280",
                "supplier_city": "Москва",
                "supplier_phone": "+7",
                "supplier_email": "sales@example.test",
                "supplier_status": "Активен",
                "item_id": "item-1",
                "item_name": "Кофе-брейк",
                "category": "Питание",
                "unit": "чел",
                "unit_price": 450.0,
                "source_text": "Кофе и чай",
                "section": "Кейтеринг",
                "has_vat": "В т.ч. НДС",
                "service_type": "catering",
                "unit_kind": "person",
                "quantity_kind": "per_guest",
            }
        ]
        conn = _Connection(rows)
        store = PostgresCatalogStore(Settings(database_url="postgresql://test"))

        with patch.object(store, "_connect", return_value=conn):
            supplier = store.get_supplier("7704856280")

        detail_sql, detail_params = conn.calls[-1]
        self.assertIn("WHERE s.id = %s", detail_sql)
        self.assertIn("ORDER BY pi.service_type, pi.category, pi.name", detail_sql)
        self.assertEqual(detail_params, ("7704856280",))
        self.assertEqual(supplier["id"], "7704856280")
        self.assertEqual(supplier["name"], "ООО Питание")
        self.assertEqual(supplier["items"][0]["id"], "item-1")
        self.assertEqual(supplier["items"][0]["unit_price"], 450.0)

    def test_get_supplier_returns_none_for_unknown_supplier(self):
        conn = _Connection([])
        store = PostgresCatalogStore(Settings(database_url="postgresql://test"))

        with patch.object(store, "_connect", return_value=conn):
            supplier = store.get_supplier("missing")

        self.assertIsNone(supplier)

    def test_list_suppliers_wraps_schema_failures_as_dependency_unavailable(self):
        store = PostgresCatalogStore(Settings(database_url="postgresql://test"))

        with patch.object(store, "ensure_schema", side_effect=RuntimeError("schema failed")):
            with self.assertRaises(DependencyUnavailableError) as ctx:
                store.list_suppliers()

        self.assertIn("список поставщиков", str(ctx.exception))

    def test_get_supplier_wraps_schema_failures_as_dependency_unavailable(self):
        store = PostgresCatalogStore(Settings(database_url="postgresql://test"))

        with patch.object(store, "ensure_schema", side_effect=RuntimeError("schema failed")):
            with self.assertRaises(DependencyUnavailableError) as ctx:
                store.get_supplier("7704856280")

        self.assertIn("получить поставщика", str(ctx.exception))


if __name__ == "__main__":
    unittest.main()
