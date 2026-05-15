import unittest

from pydantic import ValidationError

from app.brief import BriefState
from app.router import (
    RouterDecision,
    build_router_prompt,
    heuristic_route,
    parse_router_decision,
)


class RouterTests(unittest.TestCase):
    def test_parse_router_decision_accepts_only_schema_fields(self):
        decision = parse_router_decision(
            """
            {
              "interface_mode": "chat_search",
              "intent": "supplier_search",
              "workflow_stage": "searching",
              "confidence": 0.91,
              "reason_codes": ["catalog_search"],
              "brief_update": {},
              "search_requests": [
                {
                  "query": "радиомикрофон",
                  "service_category": "звук",
                  "filters": {
                    "supplier_city_normalized": "екатеринбург",
                    "category": null,
                    "supplier_status_normalized": null,
                    "has_vat": null,
                    "vat_mode": null,
                    "unit_price_min": null,
                    "unit_price_max": 5000
                  },
                  "priority": 1,
                  "limit": 8
                }
              ],
              "tool_intents": ["search_items"],
              "missing_fields": [],
              "clarification_questions": []
            }
            """
        )

        self.assertIsInstance(decision, RouterDecision)
        self.assertEqual(decision.interface_mode, "chat_search")
        self.assertEqual(decision.search_requests[0].query, "радиомикрофон")
        self.assertEqual(
            decision.search_requests[0].filters.supplier_city_normalized,
            "екатеринбург",
        )

    def test_parse_router_decision_rejects_unknown_fields(self):
        with self.assertRaises(ValidationError):
            parse_router_decision(
                """
                {
                  "interface_mode": "chat_search",
                  "intent": "supplier_search",
                  "workflow_stage": "searching",
                  "confidence": 0.91,
                  "reason_codes": [],
                  "brief_update": {},
                  "search_requests": [],
                  "tool_intents": [],
                  "missing_fields": [],
                  "clarification_questions": [],
                  "extra": "not allowed"
                }
                """
            )

    def test_build_router_prompt_includes_backend_context(self):
        state = BriefState(city="Москва", guests_count=100)

        prompt = build_router_prompt(
            message="Покажи подрядчиков по звуку",
            brief_state=state,
            visible_candidates=[{"payload": {"id": "664"}}],
            ui_mode="brief",
        )

        self.assertIn("ui_mode=brief", prompt)
        self.assertIn("Покажи подрядчиков по звуку", prompt)
        self.assertIn('"city": "Москва"', prompt)
        self.assertIn('"id": "664"', prompt)

    def test_heuristic_route_uses_search_mode_as_hint_not_source_of_truth(self):
        decision = heuristic_route(
            "Найди радиомикрофоны в Екатеринбурге до 5000",
            brief_state=BriefState(),
            ui_mode="brief",
        )

        self.assertEqual(decision.interface_mode, "chat_search")
        self.assertEqual(decision.intent, "supplier_search")
        self.assertEqual(decision.search_requests[0].query, "радиомикрофон")
        self.assertEqual(
            decision.search_requests[0].filters.supplier_city_normalized,
            "екатеринбург",
        )
        self.assertEqual(decision.search_requests[0].filters.unit_price_max, 5000)


if __name__ == "__main__":
    unittest.main()
