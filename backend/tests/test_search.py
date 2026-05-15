import json
import unittest

from app.errors import DependencyUnavailableError
from app.search import PriceSearcher


class FakeLMClient:
    def __init__(self, rerank_response):
        self.inputs = None
        self.complete_calls = []
        self.rerank_response = rerank_response

    def embed(self, inputs):
        self.inputs = inputs
        return [[0.1, 0.2, 0.3]]

    def complete(self, system, user):
        self.complete_calls.append({"system": system, "user": user})
        return self.rerank_response


class FakeStore:
    def __init__(self, semantic_results, lexical_results=None):
        self.semantic_results = semantic_results
        self.lexical_results = lexical_results if lexical_results is not None else []
        self.query_vector = None
        self.semantic_limit = None
        self.lexical_query = None
        self.lexical_limit = None
        self.semantic_filters = None
        self.lexical_filters = None

    def search(self, query_vector, limit=10, filters=None):
        self.query_vector = query_vector
        self.semantic_limit = limit
        self.semantic_filters = filters
        return self._filtered(self.semantic_results, filters)[:limit]

    def lexical_search(self, query, limit=10, filters=None):
        self.lexical_query = query
        self.lexical_limit = limit
        self.lexical_filters = filters
        return self._filtered(self.lexical_results, filters)[:limit]

    def _filtered(self, results, filters):
        filtered = results
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
        return filtered


def _rerank_response(*scores):
    items = [{"id": item_id, "score": score, "reason": "test"} for item_id, score in scores]
    return json.dumps({"items": items}, ensure_ascii=False)


def make_searcher(semantic_results, lexical_results=None, rerank_response=None):
    searcher = PriceSearcher.__new__(PriceSearcher)
    searcher.lm = FakeLMClient(rerank_response or _rerank_response())
    searcher.store = FakeStore(semantic_results, lexical_results)
    return searcher


class PriceSearcherTests(unittest.TestCase):
    def test_fetches_eighty_semantic_and_lexical_candidates_then_llm_reranks_top_limit(self):
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
            ],
            rerank_response=_rerank_response(("256", 1.0), ("45", 0.7), ("900", 0.4), ("901", 0.1)),
        )

        results = searcher.search("ужин на 30 человек", limit=3)

        self.assertEqual(searcher.lm.inputs, ["ужин на 30 человек"])
        self.assertEqual(searcher.store.query_vector, [0.1, 0.2, 0.3])
        self.assertEqual(searcher.store.semantic_limit, 80)
        self.assertEqual(searcher.store.lexical_query, "ужин на 30 человек")
        self.assertEqual(searcher.store.lexical_limit, 80)
        self.assertEqual(len(searcher.lm.complete_calls), 1)
        self.assertIn('"query": "ужин на 30 человек"', searcher.lm.complete_calls[0]["user"])
        self.assertIn('"id": "256"', searcher.lm.complete_calls[0]["user"])
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
            ],
            rerank_response=_rerank_response(("664", 1.0)),
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
            ],
            rerank_response=_rerank_response(("557", 1.0)),
        )

        results = searcher.search(
            "кофе-брейк для конференции",
            limit=3,
            filters={"service_type": "catering", "city": "москва", "only_active": True},
        )

        self.assertEqual(searcher.store.semantic_limit, 80)
        self.assertEqual(
            searcher.store.semantic_filters,
            {"service_type": "catering", "city": "москва", "only_active": True},
        )
        self.assertEqual(
            searcher.store.lexical_filters,
            {"service_type": "catering", "city": "москва", "only_active": True},
        )
        self.assertEqual([item["payload"]["id"] for item in results], ["557"])

    def test_lexical_only_candidate_can_enter_final_results_after_rrf_merge(self):
        searcher = make_searcher(
            semantic_results=[
                {
                    "score": 0.8,
                    "payload": {
                        "id": "semantic",
                        "name": "Ужин",
                        "source_text": "Организация ужина",
                    },
                }
            ],
            lexical_results=[
                {
                    "score": 0.95,
                    "payload": {
                        "id": "lexical",
                        "name": "Кофе-брейк",
                        "source_text": "Кофе-брейк на 30 человек в Москве",
                    },
                }
            ],
            rerank_response=_rerank_response(("lexical", 1.0), ("semantic", 0.2)),
        )

        results = searcher.search("кофе-брейк на 30 человек", limit=2)

        self.assertEqual([item["payload"]["id"] for item in results], ["lexical", "semantic"])

    def test_duplicate_semantic_and_lexical_candidates_are_returned_once(self):
        duplicated = {
            "score": 0.8,
            "payload": {
                "id": "same",
                "name": "Радиомикрофон",
                "source_text": "Радиомикрофон для конференции",
            },
        }
        searcher = make_searcher(
            semantic_results=[duplicated],
            lexical_results=[duplicated],
            rerank_response=_rerank_response(("same", 1.0)),
        )

        results = searcher.search("радиомикрофон", limit=5)

        self.assertEqual([item["payload"]["id"] for item in results], ["same"])

    def test_exact_source_text_numbers_and_city_break_llm_score_ties(self):
        searcher = make_searcher(
            semantic_results=[
                {
                    "score": 0.99,
                    "payload": {
                        "id": "generic",
                        "name": "Кофе-брейк",
                        "source_text": "Кофе, чай и выпечка",
                        "supplier_city": "Санкт-Петербург",
                        "city_normalized": "санкт-петербург",
                    },
                },
                {
                    "score": 0.6,
                    "payload": {
                        "id": "exact",
                        "name": "Организация питания",
                        "source_text": "Кофе-брейк на 30 человек в Москве",
                        "supplier_city": "Москва",
                        "city_normalized": "москва",
                    },
                },
            ],
            rerank_response=_rerank_response(("generic", 0.5), ("exact", 0.5)),
        )

        results = searcher.search("кофе-брейк на 30 человек в Москве", limit=2)

        self.assertEqual([item["payload"]["id"] for item in results], ["exact", "generic"])

    def test_llm_rerank_receives_only_top_twenty_candidates(self):
        semantic_results = [
            {"score": 1 - index / 100, "payload": {"id": f"item-{index}", "name": f"Позиция {index}"}}
            for index in range(25)
        ]
        searcher = make_searcher(
            semantic_results=semantic_results,
            rerank_response=_rerank_response(*[(f"item-{index}", 1 - index / 100) for index in range(20)]),
        )

        searcher.search("позиция", limit=5)

        prompt = searcher.lm.complete_calls[0]["user"]
        self.assertIn('"id": "item-19"', prompt)
        self.assertNotIn('"id": "item-20"', prompt)

    def test_invalid_llm_rerank_json_raises_dependency_unavailable(self):
        searcher = make_searcher(
            semantic_results=[{"score": 0.8, "payload": {"id": "1", "name": "Кофе-брейк"}}],
            rerank_response="not json",
        )

        with self.assertRaises(DependencyUnavailableError) as ctx:
            searcher.search("кофе-брейк", limit=1)

        self.assertIn("LLM rerank", str(ctx.exception))


if __name__ == "__main__":
    unittest.main()
