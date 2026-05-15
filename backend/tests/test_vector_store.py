import unittest
from unittest.mock import patch

from app.config import Settings
from app.vector_store import QdrantPriceStore


class _Point:
    def __init__(self, score, payload):
        self.score = score
        self.payload = payload


class _QueryResponse:
    points = [
        _Point(0.91, {"id": "42", "name": "Ужин"}),
        _Point(0.73, None),
    ]


class _FakeQdrantClient:
    last_instance = None

    def __init__(self, **kwargs):
        self.kwargs = kwargs
        self.query_calls = []
        _FakeQdrantClient.last_instance = self

    def query_points(self, **kwargs):
        self.query_calls.append(kwargs)
        return _QueryResponse()


class QdrantPriceStoreTests(unittest.TestCase):
    def test_search_uses_query_points_api(self):
        settings = Settings(qdrant_url="http://qdrant.test:6333", qdrant_collection="prices")

        with patch("app.vector_store.QdrantClient", _FakeQdrantClient):
            store = QdrantPriceStore(settings)
            results = store.search([0.1, 0.2, 0.3], limit=2)

        client = _FakeQdrantClient.last_instance
        self.assertEqual(
            client.query_calls,
            [
                {
                    "collection_name": "prices",
                    "query": [0.1, 0.2, 0.3],
                    "limit": 2,
                    "with_payload": True,
                }
            ],
        )
        self.assertEqual(
            results,
            [
                {"score": 0.91, "payload": {"id": "42", "name": "Ужин"}},
                {"score": 0.73, "payload": {}},
            ],
        )

    def test_search_passes_payload_filter_to_qdrant(self):
        settings = Settings(qdrant_url="http://qdrant.test:6333", qdrant_collection="prices")

        with patch("app.vector_store.QdrantClient", _FakeQdrantClient):
            store = QdrantPriceStore(settings)
            store.search(
                [0.1, 0.2, 0.3],
                limit=3,
                filters={"service_type": "catering", "city": "москва", "only_active": True},
            )

        query_filter = _FakeQdrantClient.last_instance.query_calls[0]["query_filter"]
        conditions = query_filter.must
        self.assertEqual(conditions[0].key, "service_type")
        self.assertEqual(conditions[0].match.value, "catering")
        self.assertEqual(conditions[1].key, "city_normalized")
        self.assertEqual(conditions[1].match.value, "москва")
        self.assertEqual(conditions[2].key, "supplier_status_normalized")
        self.assertEqual(conditions[2].match.value, "активен")


if __name__ == "__main__":
    unittest.main()
