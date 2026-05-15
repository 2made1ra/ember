import unittest

from app.brief import BriefState, budget_lines_from_results, estimate_budget


class BudgetTests(unittest.TestCase):
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

    def test_estimate_budget_uses_catalog_prices_quantities_and_multipliers(self):
        result = estimate_budget(
            [
                {
                    "item_id": "557",
                    "name": "Организация кофе-брейка",
                    "unit": "шт",
                    "unit_price": 500,
                    "quantity": 100,
                    "multiplier": 2,
                    "comment": "2 кофе-брейка на 100 гостей",
                },
                {
                    "item_id": "556",
                    "name": "Организация обеда",
                    "unit": "шт",
                    "unit_price": 886.5,
                    "quantity": 100,
                },
            ]
        )

        self.assertEqual(result["total"], 188650.0)
        self.assertEqual(result["lines"][0]["subtotal"], 100000.0)
        self.assertEqual(result["lines"][1]["subtotal"], 88650.0)

    def test_budget_lines_include_selected_candidate_items_without_fresh_results(self):
        state = BriefState(guests_count=100)
        selected_item = self._catalog_item(
            "c1",
            "Кофе-брейк базовый",
            "Комбинат питания",
            "catering",
            unit_price=500,
            quantity_kind="per_guest",
        )
        state.service_needs["catering"].selected_item_ids = ["c1"]
        state.service_needs["catering"].candidate_items = [selected_item]

        lines = budget_lines_from_results([], state)

        self.assertEqual([line["item_id"] for line in lines], ["c1"])
        self.assertEqual(lines[0]["name"], "Кофе-брейк базовый")
        self.assertEqual(lines[0]["guests_count"], 100)

    def test_budget_lines_include_selected_price_items_without_fresh_results(self):
        state = BriefState(guests_count=100)
        state.selected_price_items = [
            self._catalog_item(
                "c1",
                "Кофе-брейк базовый",
                "Комбинат питания",
                "catering",
                unit_price=500,
                quantity_kind="per_guest",
            )
        ]

        lines = budget_lines_from_results([], state)

        self.assertEqual([line["item_id"] for line in lines], ["c1"])
        self.assertEqual(lines[0]["supplier"], "Комбинат питания")

    def test_budget_lines_include_multiple_selected_items_from_same_service(self):
        state = BriefState(guests_count=100)
        coffee = self._catalog_item(
            "c1",
            "Кофе-брейк базовый",
            "Комбинат питания",
            "catering",
            unit_price=500,
            quantity_kind="per_guest",
        )
        lunch = self._catalog_item(
            "c2",
            "Обед",
            "Fresh Food",
            "catering",
            unit_price=900,
            quantity_kind="per_guest",
        )
        state.service_needs["catering"].selected_item_ids = ["c1", "c2"]

        lines = budget_lines_from_results([coffee, lunch], state)

        self.assertEqual([line["item_id"] for line in lines], ["c1", "c2"])
        self.assertEqual([line["service_type"] for line in lines], ["catering", "catering"])


if __name__ == "__main__":
    unittest.main()
