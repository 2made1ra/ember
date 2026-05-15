import unittest
from importlib import import_module, util

from app.agent import run_argus_turn
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
    def _catalog_item(
        self,
        item_id,
        name,
        supplier,
        service_type,
        unit_price=1000,
        unit="шт",
        quantity_kind="fixed",
    ):
        return {
            "score": 0.8,
            "payload": {
                "id": item_id,
                "name": name,
                "category": service_type,
                "unit": unit,
                "unit_price": unit_price,
                "supplier": supplier,
                "service_type": service_type,
                "quantity_kind": quantity_kind,
            },
        }

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
            [("catering", 5), ("av_equipment", 5)],
        )
        self.assertTrue(all(call["filters"]["city"] == "москва" for call in searcher.calls))
        self.assertEqual(response["found_items"][0]["payload"]["id"], "557")
        self.assertIn("ID 557", response["message"])
        self.assertIn("ID 664", response["message"])

    def test_brief_search_stores_shortlists_grouped_by_service_and_supplier(self):
        catering_items = [
            self._catalog_item("c1", "Кофе-брейк базовый", "Комбинат питания", "catering"),
            self._catalog_item("c2", "Кофе-брейк расширенный", "Комбинат питания", "catering"),
            self._catalog_item("c3", "Фуршет", "Fresh Food", "catering"),
            self._catalog_item("c4", "Обед", "Fresh Food", "catering"),
            self._catalog_item("c5", "Ужин", "Event Catering", "catering"),
        ]
        av_items = [
            self._catalog_item("a1", "Радиомикрофон", "Премьер-Шоу", "av_equipment"),
            self._catalog_item("a2", "Звуковой комплект", "Премьер-Шоу", "av_equipment"),
            self._catalog_item("a3", "Экран", "AV Profi", "av_equipment"),
            self._catalog_item("a4", "Проектор", "AV Profi", "av_equipment"),
            self._catalog_item("a5", "Световой комплект", "Light Team", "av_equipment"),
        ]
        searcher = RecordingSearcher({"catering": catering_items, "av_equipment": av_items})
        state = BriefState()

        response = run_brief_turn(
            state=state,
            message=(
                "Нужна офлайн конференция в Москве на 100 человек. "
                "Планируем кофе-брейк, фуршет, звук и радиомикрофоны. Бюджет стандарт."
            ),
            searcher=searcher,
            chat_client=None,
        )

        service_needs = response["brief_state"]["service_needs"]
        self.assertEqual(len(service_needs["catering"]["candidate_items"]), 5)
        self.assertEqual(len(service_needs["av_equipment"]["candidate_items"]), 5)
        self.assertTrue(all(call["limit"] >= 5 for call in searcher.calls))
        self.assertIn("Короткий список подрядчиков", response["message"])
        self.assertIn("Питание", response["message"])
        self.assertIn("Оборудование и AV", response["message"])
        self.assertIn("Комбинат питания", response["message"])
        self.assertIn("Fresh Food", response["message"])
        self.assertIn("Премьер-Шоу", response["message"])
        self.assertIn("AV Profi", response["message"])
        self.assertLess(
            response["message"].index("Комбинат питания"),
            response["message"].index("Fresh Food"),
        )
        self.assertLess(
            response["message"].index("Премьер-Шоу"),
            response["message"].index("AV Profi"),
        )

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
        self.assertEqual(response["budget"]["lines"], [])
        self.assertNotIn("Предварительная смета", response["message"])
        self.assertNotIn("= 50 000 ₽", response["message"])

    def test_selected_candidate_survives_later_catalog_search_for_budget(self):
        selected_item = self._catalog_item(
            "c1",
            "Кофе-брейк базовый",
            "Комбинат питания",
            "catering",
            unit_price=500,
            quantity_kind="per_guest",
        )
        replacement_item = self._catalog_item(
            "c2",
            "Кофе-брейк расширенный",
            "Fresh Food",
            "catering",
            unit_price=800,
            quantity_kind="per_guest",
        )
        state = BriefState(
            event_type="конференция",
            city="Москва",
            guests_count=100,
            format="офлайн",
            budget_tier="стандарт",
        )
        state.service_needs["catering"].status = "needed"
        state.service_needs["catering"].selected_item_ids = ["c1"]
        state.service_needs["catering"].candidate_items = [selected_item]
        searcher = RecordingSearcher({"catering": [replacement_item]})

        response = run_brief_turn(
            state=state,
            message="Нужен еще один поиск по кофе-брейку для конференции.",
            searcher=searcher,
            chat_client=None,
        )

        self.assertEqual(response["found_items"][0]["payload"]["id"], "c2")
        self.assertEqual(
            [line["item_id"] for line in response["budget"]["lines"]],
            ["c1"],
        )
        self.assertEqual(response["budget"]["total"], 50000.0)

    def test_selection_route_selects_visible_candidate_and_next_budget_uses_it(self):
        candidate = self._catalog_item(
            "557",
            "Организация кофе-брейка",
            "Комбинат питания",
            "catering",
            unit_price=500,
            quantity_kind="per_guest",
        )
        state = BriefState(
            event_type="конференция",
            city="Москва",
            guests_count=100,
            format="офлайн",
            budget_tier="стандарт",
        )
        state.service_needs["catering"].status = "needed"
        state.service_needs["catering"].candidate_items = [candidate]
        searcher = RecordingSearcher({"catering": []})

        selection = run_argus_turn(
            state=state,
            message="Выбери ID 557",
            searcher=searcher,
            chat_client=None,
            ui_mode="brief",
        )
        self.assertEqual(searcher.calls, [])

        budget_response = run_argus_turn(
            state=state,
            message="Собери смету по выбранным позициям",
            searcher=searcher,
            chat_client=None,
            ui_mode="brief",
        )

        self.assertEqual(selection["route"]["intent"], "selection")
        self.assertEqual(
            selection["brief_state"]["service_needs"]["catering"]["selected_item_ids"],
            ["557"],
        )
        self.assertEqual(
            [line["item_id"] for line in budget_response["budget"]["lines"]],
            ["557"],
        )
        self.assertEqual(budget_response["budget"]["total"], 50000.0)
        self.assertIn("Организация кофе-брейка", budget_response["message"])

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
