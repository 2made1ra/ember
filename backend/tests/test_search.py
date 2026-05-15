import unittest

from app.search import PriceSearcher


class FakeEmbeddingClient:
    def __init__(self):
        self.inputs = None

    def embed(self, inputs):
        self.inputs = inputs
        return [[0.1, 0.2, 0.3]]


class FakeStore:
    def __init__(self, results):
        self.results = results
        self.query_vector = None
        self.limit = None
        self.filters = None

    def search(self, query_vector, limit=10, filters=None):
        self.query_vector = query_vector
        self.limit = limit
        self.filters = filters
        filtered = self.results
        if filters:
            if filters.get("service_type"):
                filtered = [
                    item
                    for item in filtered
                    if item["payload"].get("service_type") == filters["service_type"]
                ]
            if filters.get("city"):
                filtered = [
                    item
                    for item in filtered
                    if item["payload"].get("city_normalized") == filters["city"]
                ]
            if filters.get("only_active"):
                filtered = [
                    item
                    for item in filtered
                    if item["payload"].get("supplier_status_normalized") == "активен"
                ]
        return filtered[:limit]


def make_searcher(results):
    searcher = PriceSearcher.__new__(PriceSearcher)
    searcher.lm = FakeEmbeddingClient()
    searcher.store = FakeStore(results)
    return searcher


class PriceSearcherTests(unittest.TestCase):
    def test_fetches_twenty_candidates_then_returns_reranked_top_limit(self):
        searcher = make_searcher(
            [
                {
                    "score": 0.92,
                    "payload": {
                        "id": "45",
                        "name": "Аренда барабанов",
                        "category": "Музыка",
                        "section": "Инструменты",
                        "source_text": "30 африканских барабанов",
                    },
                },
                {
                    "score": 0.7,
                    "payload": {
                        "id": "256",
                        "name": "Ужин на 1 человека",
                        "category": "Питание",
                        "section": "Ужин",
                        "source_text": "Организация ужина для гостей",
                    },
                },
                {
                    "score": 0.66,
                    "payload": {
                        "id": "900",
                        "name": "Обед",
                        "category": "Питание",
                        "section": "Обед",
                    },
                },
                {
                    "score": 0.65,
                    "payload": {
                        "id": "901",
                        "name": "Кофе-брейк",
                        "category": "Питание",
                        "section": "Кофе",
                    },
                },
            ]
        )

        results = searcher.search("ужин на 30 человек", limit=3)

        self.assertEqual(searcher.lm.inputs, ["ужин на 30 человек"])
        self.assertEqual(searcher.store.query_vector, [0.1, 0.2, 0.3])
        self.assertEqual(searcher.store.limit, 20)
        self.assertEqual([item["payload"]["id"] for item in results], ["256", "45", "900"])

    def test_preserves_full_payload_when_reranking(self):
        searcher = make_searcher(
            [
                {
                    "score": 0.7,
                    "payload": {
                        "id": "664",
                        "name": "Радиомикрофон",
                        "category": "Техническое оборудование",
                        "unit": "шт",
                        "unit_price": 1230,
                        "source_text": "Радиомикрофон для конференции",
                        "section": "Звук",
                        "supplier": "ООО ПРЕМЬЕР-ШОУ",
                        "has_vat": "В т.ч. НДС",
                        "supplier_inn": "1234567890",
                        "supplier_city": "Санкт-Петербург",
                        "supplier_phone": "+7 000 000-00-00",
                        "supplier_email": "sales@example.test",
                        "supplier_status": "Активен",
                    },
                }
            ]
        )

        results = searcher.search("радиомикрофон для конференции", limit=3)

        self.assertEqual(results[0]["payload"]["supplier_phone"], "+7 000 000-00-00")
        self.assertEqual(results[0]["payload"]["supplier_email"], "sales@example.test")
        self.assertEqual(results[0]["payload"]["source_text"], "Радиомикрофон для конференции")

    def test_applies_payload_filters_before_reranking(self):
        searcher = make_searcher(
            [
                {
                    "score": 0.99,
                    "payload": {
                        "id": "med",
                        "name": "Медицинская организация",
                        "service_type": "other",
                        "city_normalized": "москва",
                        "supplier_status_normalized": "активен",
                    },
                },
                {
                    "score": 0.72,
                    "payload": {
                        "id": "557",
                        "name": "Организация кофе-брейка",
                        "category": "Питание",
                        "section": "Кофе-брейк",
                        "service_type": "catering",
                        "city_normalized": "москва",
                        "supplier_status_normalized": "активен",
                    },
                },
                {
                    "score": 0.71,
                    "payload": {
                        "id": "999",
                        "name": "Организация обеда",
                        "category": "Питание",
                        "section": "Обед",
                        "service_type": "catering",
                        "city_normalized": "санкт-петербург",
                        "supplier_status_normalized": "активен",
                    },
                },
            ]
        )

        results = searcher.search(
            "кофе-брейк для конференции",
            limit=3,
            filters={"service_type": "catering", "city": "москва", "only_active": True},
        )

        self.assertEqual(searcher.store.limit, 20)
        self.assertEqual(
            searcher.store.filters,
            {"service_type": "catering", "city": "москва", "only_active": True},
        )
        self.assertEqual([item["payload"]["id"] for item in results], ["557"])


if __name__ == "__main__":
    unittest.main()
