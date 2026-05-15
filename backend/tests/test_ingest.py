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
    vector_size = None
    upserted_vectors = None

    def __init__(self, settings):
        pass

    def recreate_collection(self, vector_size):
        FakeStore.vector_size = vector_size

    def upsert_items(self, items, vectors):
        FakeStore.upserted_vectors = vectors


class IngestTests(unittest.TestCase):
    def setUp(self):
        reset_app_state()
        FakeStore.vector_size = None
        FakeStore.upserted_vectors = None

    def test_ingest_uses_csv_embeddings_without_calling_embedding_client(self):
        settings = Settings()

        with (
            patch("app.ingest.QdrantPriceStore", FakeStore),
            patch("app.ingest.LMStudioClient", create=True) as lm_client,
        ):
            ingest_catalog(csv_with_embeddings(), settings)

        lm_client.assert_not_called()
        self.assertEqual(FakeStore.vector_size, 3)
        self.assertEqual(FakeStore.upserted_vectors, [[0.1, 0.2, 0.3]])
        status = get_catalog_status()
        self.assertTrue(status.ready)
        self.assertEqual(status.embedded_count, 1)


if __name__ == "__main__":
    unittest.main()
