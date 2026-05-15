import unittest

from app.brief import estimate_budget


class BudgetTests(unittest.TestCase):
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


if __name__ == "__main__":
    unittest.main()
