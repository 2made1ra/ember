import csv
import io
import unittest
from unittest.mock import patch

from app.config import Settings
from app.ingest import ingest_catalog
from app.state import get_catalog_status, reset_app_state


def csv_with_embeddings() -> bytes:
    buf = io.StringIO()
    fields = [
        "id",
        "name",
        "category",
        "unit",
        "unit_price",
        "source_text",
        "section",
        "supplier",
        "has_vat",
        "embedding",
        "supplier_inn",
        "supplier_city",
        "supplier_phone",
        "supplier_email",
        "supplier_status",
    ]
    writer = csv.DictWriter(buf, fieldnames=fields)
    writer.writeheader()
    writer.writerow(
        {
            "id": "557",
            "name": "Организация кофе-брейка",
            "category": "Питание",
            "unit": "шт",
            "unit_price": "500",
            "source_text": "Кофе и выпечка",
            "section": "Кофе-брейк",
            "supplier": "ФГБУ «Комбинат питания»",
            "has_vat": "В т.ч. НДС",
            "embedding": "[0.1, 0.2, 0.3]",
            "supplier_inn": "770485628",
            "supplier_city": "Санкт-Петербург",
            "supplier_phone": "+7",
            "supplier_email": "mail@example.test",
            "supplier_status": "Активен",
        }
    )
    return buf.getvalue().encode("utf-8")


class FakeStore:
    items = None

    def __init__(self, settings):
        pass

    def replace_catalog(self, items):
        FakeStore.items = items


class IngestTests(unittest.TestCase):
    def setUp(self):
        reset_app_state()
        FakeStore.items = None

    def test_ingest_replaces_pgvector_catalog_with_csv_embeddings_without_calling_embedding_client(self):
        settings = Settings()

        with (
            patch("app.ingest.PostgresCatalogStore", FakeStore),
            patch("app.ingest.LMStudioClient", create=True) as lm_client,
        ):
            ingest_catalog(csv_with_embeddings(), settings)

        lm_client.assert_not_called()
        self.assertEqual([item.vector for item in FakeStore.items], [[0.1, 0.2, 0.3]])
        status = get_catalog_status()
        self.assertTrue(status.ready)
        self.assertEqual(status.embedded_count, 1)


if __name__ == "__main__":
    unittest.main()
