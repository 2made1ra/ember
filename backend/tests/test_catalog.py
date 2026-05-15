import csv
import io
import unittest

from app.catalog import (
    CatalogValidationError,
    parse_catalog_csv,
    parse_embedding,
    parse_unit_price,
)


class CatalogTests(unittest.TestCase):
    def test_parse_unit_price_accepts_comma_dot_and_empty_values(self):
        self.assertEqual(parse_unit_price("886,5"), 886.5)
        self.assertEqual(parse_unit_price("660"), 660.0)
        self.assertEqual(parse_unit_price(""), 0.0)

    def test_parse_catalog_rejects_missing_required_columns(self):
        buf = io.StringIO()
        writer = csv.DictWriter(buf, fieldnames=["id", "name", "unit_price"])
        writer.writeheader()
        writer.writerow({"id": "1", "name": "Позиция", "unit_price": "100"})

        with self.assertRaises(CatalogValidationError) as ctx:
            parse_catalog_csv(buf.getvalue().encode("utf-8"))

        self.assertIn("missing required columns", str(ctx.exception))

    def test_parse_catalog_keeps_embedding_out_of_payload(self):
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
                "id": "556",
                "name": "Организация обеда",
                "category": "Питание",
                "unit": "шт",
                "unit_price": "886.5",
                "source_text": "150 | Рис отварной",
                "section": "Обед",
                "supplier": "ФГБУ «Комбинат питания»",
                "has_vat": "В т.ч. НДС",
                "embedding": "[1, 2, 3]",
                "supplier_inn": "770485628",
                "supplier_city": "Санкт-Петербург",
                "supplier_phone": "+7",
                "supplier_email": "mail@example.test",
                "supplier_status": "Активен",
            }
        )

        items = parse_catalog_csv(buf.getvalue().encode("utf-8"))

        self.assertEqual(len(items), 1)
        self.assertEqual(items[0].id, "556")
        self.assertEqual(items[0].unit_price, 886.5)
        self.assertNotIn("embedding", items[0].payload)

    def test_parse_embedding_reads_json_float_vector(self):
        self.assertEqual(parse_embedding("[1, 2.5, -0.25]"), [1.0, 2.5, -0.25])

    def test_parse_catalog_uses_existing_embedding_vector(self):
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

        items = parse_catalog_csv(buf.getvalue().encode("utf-8"))

        self.assertEqual(items[0].vector, [0.1, 0.2, 0.3])

    def test_parse_catalog_adds_brief_payload_fields(self):
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
                "id": "664",
                "name": "Радиомикрофон",
                "category": "Оборудование",
                "unit": "шт",
                "unit_price": "1230",
                "source_text": "Радиомикрофон для конференции",
                "section": "ЗВУК",
                "supplier": "ООО ПРЕМЬЕР-ШОУ",
                "has_vat": "В т.ч. НДС",
                "embedding": "[0.1, 0.2, 0.3]",
                "supplier_inn": "1234567890",
                "supplier_city": "г. Санкт-Петербург",
                "supplier_phone": "+7",
                "supplier_email": "sales@example.test",
                "supplier_status": "Активен",
            }
        )

        item = parse_catalog_csv(buf.getvalue().encode("utf-8"))[0]

        self.assertEqual(item.payload["service_type"], "av_equipment")
        self.assertEqual(item.payload["city_normalized"], "санкт-петербург")
        self.assertEqual(item.payload["supplier_status_normalized"], "активен")
        self.assertEqual(item.payload["unit_kind"], "piece")
        self.assertEqual(item.payload["quantity_kind"], "fixed")


if __name__ == "__main__":
    unittest.main()
