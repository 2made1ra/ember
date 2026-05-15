import unittest

from app.semantic_agent import format_price_item, run_semantic_search_agent


class FakeSearcher:
    last_query = None
    last_limit = None

    def search(self, query, limit=8):
        FakeSearcher.last_query = query
        FakeSearcher.last_limit = limit
        return [
            {
                "score": 0.561,
                "payload": {
                    "id": "664",
                    "name": "Радиомикрофон (аренда за 1 день)",
                    "category": "Техническое оборудование",
                    "section": "Звук",
                    "unit": "шт",
                    "unit_price": 1230,
                    "supplier": "ООО ПРЕМЬЕР-ШОУ",
                    "supplier_city": "Санкт-Петербург",
                    "source_text": "Радиомикрофон для мероприятия",
                },
            }
        ]


class SemanticAgentTests(unittest.TestCase):
    def setUp(self):
        FakeSearcher.last_query = None
        FakeSearcher.last_limit = None

    def test_formats_catalog_item_as_human_readable_text_without_score(self):
        line = format_price_item(
            {
                "score": 0.561,
                "payload": {
                    "id": "664",
                    "name": "Радиомикрофон (аренда за 1 день)",
                    "category": "Техническое оборудование",
                    "section": "Звук",
                    "unit": "шт",
                    "unit_price": 1230,
                    "supplier": "ООО ПРЕМЬЕР-ШОУ",
                    "supplier_city": "Санкт-Петербург",
                    "source_text": "Радиомикрофон для мероприятия",
                },
            },
            1,
        )

        self.assertEqual(
            line,
            "1. Радиомикрофон (аренда за 1 день) — 1 230 ₽ за шт. "
            "Поставщик: ООО ПРЕМЬЕР-ШОУ, Санкт-Петербург. "
            "Категория: Техническое оборудование / Звук. ID 664.",
        )
        self.assertNotIn("score", line.lower())
        self.assertNotIn("0.561", line)

    def test_semantic_agent_searches_and_returns_message(self):
        result = run_semantic_search_agent(
            query="радиомикрофон и звук для конференции",
            searcher=FakeSearcher(),
            limit=3,
        )

        self.assertEqual(FakeSearcher.last_query, "радиомикрофон и звук для конференции")
        self.assertEqual(FakeSearcher.last_limit, 3)
        self.assertEqual(len(result["items"]), 1)
        self.assertTrue(result["message"].startswith("1. "))
        self.assertIn("Радиомикрофон", result["message"])
        self.assertNotIn("score", result["message"].lower())


if __name__ == "__main__":
    unittest.main()
