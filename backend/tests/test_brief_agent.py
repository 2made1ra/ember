import unittest
from importlib import import_module, util

from app.brief import BriefState, estimate_budget, run_brief_turn


class RecordingSearcher:
    def __init__(self, results=None):
        self.calls = []
        self.results = results or {}

    def search(self, query, limit=8, filters=None):
        self.calls.append({"query": query, "limit": limit, "filters": filters})
        service_type = (filters or {}).get("service_type")
        return self.results.get(service_type, [])[:limit]


class BriefAgentTests(unittest.TestCase):
    def test_prompt_contracts_are_split_by_llm_role(self):
        self.assertIsNotNone(util.find_spec("app.prompts"))
        prompts = import_module("app.prompts")

        self.assertIn("ARGUS Router", prompts.ROUTER_SYSTEM_PROMPT)
        self.assertIn("валидный JSON", prompts.ROUTER_SYSTEM_PROMPT)
        self.assertIn("ARGUS Assistant", prompts.COMPOSER_SYSTEM_PROMPT)
        self.assertIn("found_items", prompts.COMPOSER_SYSTEM_PROMPT)
        self.assertIn("reranker", prompts.RERANKER_SYSTEM_PROMPT.lower())

    def test_brief_chat_uses_composer_prompt_contract(self):
        class RecordingChatClient:
            system = None
            user = None

            def complete(self, system, user):
                RecordingChatClient.system = system
                RecordingChatClient.user = user
                return "Нужны уточнения"

        response = run_brief_turn(
            state=BriefState(),
            message="Хочу организовать мероприятие",
            searcher=RecordingSearcher(),
            chat_client=RecordingChatClient(),
        )

        self.assertEqual(response["message"], "Нужны уточнения")
        self.assertIn("ARGUS Assistant", RecordingChatClient.system)
        self.assertNotIn("ARGUS Router", RecordingChatClient.system)
        self.assertIn("Brief facts", RecordingChatClient.system)
        self.assertIn("ui_mode=brief_workspace", RecordingChatClient.user)
        self.assertIn("found_items=", RecordingChatClient.user)
        self.assertIn("Черновик ответа", RecordingChatClient.user)

    def test_generic_first_request_asks_questions_without_catalog_search(self):
        searcher = RecordingSearcher()
        state = BriefState()

        response = run_brief_turn(
            state=state,
            message="Хочу организовать мероприятие",
            searcher=searcher,
            chat_client=None,
        )

        self.assertEqual(searcher.calls, [])
        self.assertEqual(response["brief_state"]["stage"], "intake")
        self.assertIn("Какой тип мероприятия", response["message"])
        self.assertIn("город", response["message"].lower())
        self.assertIn("Сколько участников", response["message"])
        self.assertLessEqual(len(response["brief_state"]["open_questions"]), 4)

    def test_filled_request_creates_service_needs_and_searches_relevant_catalog_blocks(self):
        searcher = RecordingSearcher(
            {
                "catering": [
                    {
                        "score": 0.82,
                        "payload": {
                            "id": "557",
                            "name": "Организация кофе-брейка",
                            "category": "Питание",
                            "unit": "шт",
                            "unit_price": 500,
                            "supplier": "Комбинат питания",
                            "service_type": "catering",
                            "quantity_kind": "per_guest",
                        },
                    }
                ],
                "av_equipment": [
                    {
                        "score": 0.78,
                        "payload": {
                            "id": "664",
                            "name": "Радиомикрофон",
                            "category": "Оборудование",
                            "unit": "шт",
                            "unit_price": 1230,
                            "supplier": "Премьер-Шоу",
                            "service_type": "av_equipment",
                            "quantity_kind": "fixed",
                        },
                    }
                ],
            }
        )
        state = BriefState()

        response = run_brief_turn(
            state=state,
            message=(
                "Нужна офлайн конференция в Москве на 100 человек. "
                "Планируем кофе-брейк и звук с радиомикрофонами. Бюджет стандарт."
            ),
            searcher=searcher,
            chat_client=None,
        )

        service_needs = response["brief_state"]["service_needs"]
        self.assertEqual(service_needs["catering"]["status"], "needed")
        self.assertEqual(service_needs["av_equipment"]["status"], "needed")
        self.assertEqual(
            [(call["filters"]["service_type"], call["limit"]) for call in searcher.calls],
            [("catering", 3), ("av_equipment", 3)],
        )
        self.assertTrue(all(call["filters"]["city"] == "москва" for call in searcher.calls))
        self.assertEqual(response["found_items"][0]["payload"]["id"], "557")
        self.assertIn("ID 557", response["message"])
        self.assertIn("ID 664", response["message"])

    def test_found_items_remain_candidates_until_user_explicitly_selects_them(self):
        searcher = RecordingSearcher(
            {
                "catering": [
                    {
                        "score": 0.82,
                        "payload": {
                            "id": "557",
                            "name": "Организация кофе-брейка",
                            "category": "Питание",
                            "unit": "шт",
                            "unit_price": 500,
                            "supplier": "Комбинат питания",
                            "service_type": "catering",
                            "quantity_kind": "per_guest",
                        },
                    }
                ],
            }
        )
        state = BriefState()

        response = run_brief_turn(
            state=state,
            message=(
                "Нужна офлайн конференция в Москве на 100 человек. "
                "Планируем кофе-брейк. Бюджет стандарт."
            ),
            searcher=searcher,
            chat_client=None,
        )

        self.assertEqual(response["found_items"][0]["payload"]["id"], "557")
        self.assertEqual(
            response["brief_state"]["service_needs"]["catering"]["selected_item_ids"],
            [],
        )
        self.assertEqual(response["brief_state"]["selected_price_items"], [])
        self.assertIn("кандидат", response["message"].lower())

    def test_budget_uses_variable_and_fixed_quantity_rules(self):
        result = estimate_budget(
            [
                {
                    "item_id": "557",
                    "name": "Кофе-брейк",
                    "unit": "шт",
                    "unit_price": 500,
                    "quantity_kind": "per_guest",
                    "guests_count": 100,
                },
                {
                    "item_id": "664",
                    "name": "Радиомикрофон",
                    "unit": "шт",
                    "unit_price": 1230,
                    "quantity_kind": "fixed",
                    "guests_count": 100,
                },
                {
                    "item_id": "manual",
                    "name": "Неясная услуга",
                    "unit": "комплект",
                    "unit_price": 7000,
                    "quantity_kind": "manual_review",
                    "guests_count": 100,
                },
            ]
        )

        self.assertEqual(result["total"], 58230.0)
        self.assertEqual(result["lines"][0]["quantity"], 100)
        self.assertEqual(result["lines"][1]["quantity"], 1)
        self.assertEqual(result["lines"][2]["quantity"], 1)
        self.assertIn("ручной проверки", result["lines"][2]["comment"])


if __name__ == "__main__":
    unittest.main()
