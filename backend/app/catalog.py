from __future__ import annotations

import csv
import io
import json
import re
from dataclasses import dataclass
from typing import Any


REQUIRED_COLUMNS = {
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
}

PAYLOAD_COLUMNS = [
    "id",
    "name",
    "category",
    "unit",
    "unit_price",
    "source_text",
    "section",
    "supplier",
    "has_vat",
    "supplier_inn",
    "supplier_city",
    "supplier_phone",
    "supplier_email",
    "supplier_status",
]


class CatalogValidationError(ValueError):
    """Raised when an uploaded CSV cannot be used as a price catalog."""


@dataclass(frozen=True)
class CatalogItem:
    id: str
    embedding_text: str
    vector: list[float]
    payload: dict[str, Any]
    unit_price: float


def clean_cell(value: Any) -> str:
    return str(value or "").strip()


def normalize_city(value: Any) -> str:
    text = clean_cell(value).lower().replace("ё", "е")
    text = re.sub(r"^(г\.?|город)\s*", "", text).strip()
    text = re.sub(r"\s*-\s*", "-", text)
    text = re.sub(r"\s+", " ", text)
    return text.strip(" .,;:")


def normalize_status(value: Any) -> str:
    return clean_cell(value).lower().replace("ё", "е")


def classify_service_type(row: dict[str, Any]) -> str:
    text = " ".join(
        [
            clean_cell(row.get("name")),
            clean_cell(row.get("category")),
            clean_cell(row.get("section")),
            clean_cell(row.get("source_text")),
        ]
    ).lower()

    rules = [
        (
            "catering",
            [
                "питан",
                "кофе",
                "обед",
                "ужин",
                "фуршет",
                "кейтер",
                "меню",
                "напит",
                "банкет",
            ],
        ),
        (
            "venue",
            [
                "площад",
                "конференц-зал",
                "конференц зал",
                "помещен",
                "аренда зала",
                "аудитор",
            ],
        ),
        (
            "av_equipment",
            [
                "микроф",
                "звук",
                "свет",
                "экран",
                "проектор",
                "трансляц",
                "оборуд",
                "акуст",
                "сцен",
            ],
        ),
        ("staff", ["персонал", "хостес", "регистрац", "волонтер", "волонтёр", "охран", "техник"]),
        ("transport", ["транспорт", "трансфер", "автобус", "перевоз", "логист"]),
        ("accommodation", ["прожив", "гостиниц", "отель", "номер", "апартамент"]),
        ("branding", ["бренд", "баннер", "стенд", "навигац", "оформлен"]),
        ("print", ["полиграф", "печать", "буклет", "бейдж", "листов", "плакат", "таблич"]),
        ("merch", ["сувен", "мерч", "подар", "футбол", "ручк"]),
        ("entertainment", ["ведущ", "артист", "аниматор", "развлекатель", "музык", "барабан"]),
    ]
    for service_type, needles in rules:
        if any(needle in text for needle in needles):
            return service_type
    return "other"


def classify_unit_kind(unit: Any) -> str:
    text = clean_cell(unit).lower()
    if any(needle in text for needle in ["чел", "персон", "гост"]):
        return "person"
    if "ноч" in text:
        return "night"
    if "час" in text:
        return "hour"
    if any(needle in text for needle in ["день", "сут"]):
        return "day"
    if any(needle in text for needle in ["шт", "ед", "услуг"]):
        return "piece"
    if "комплект" in text:
        return "set"
    return "unknown"


def classify_quantity_kind(service_type: str, unit_kind: str) -> str:
    if service_type == "catering" or unit_kind == "person":
        return "per_guest"
    if service_type == "accommodation" and unit_kind == "night":
        return "per_guest_night"
    if unit_kind in {"day", "hour"}:
        return "per_day"
    if service_type in {
        "venue",
        "av_equipment",
        "staff",
        "transport",
        "branding",
        "print",
        "merch",
        "entertainment",
    }:
        return "fixed"
    if unit_kind in {"piece", "set"}:
        return "fixed"
    return "manual_review"


def parse_unit_price(value: Any) -> float:
    cleaned = clean_cell(value).replace(" ", "").replace(",", ".")
    if not cleaned:
        return 0.0
    try:
        return float(cleaned)
    except ValueError as exc:
        raise CatalogValidationError(f"invalid unit_price: {value!r}") from exc


def parse_embedding(value: Any) -> list[float]:
    raw = clean_cell(value)
    if not raw:
        raise CatalogValidationError("embedding is required")
    try:
        parsed = json.loads(raw)
    except json.JSONDecodeError as exc:
        raise CatalogValidationError("embedding must be a JSON array") from exc
    if not isinstance(parsed, list) or not parsed:
        raise CatalogValidationError("embedding must be a non-empty JSON array")
    vector: list[float] = []
    for item in parsed:
        if not isinstance(item, int | float):
            raise CatalogValidationError("embedding must contain only numbers")
        vector.append(float(item))
    return vector


def build_embedding_text(row: dict[str, Any]) -> str:
    parts = [
        clean_cell(row.get("name")),
        clean_cell(row.get("unit")),
        clean_cell(row.get("category")),
        clean_cell(row.get("section")),
        clean_cell(row.get("supplier")),
    ]
    return " ".join(part for part in parts if part)


def validate_columns(fieldnames: list[str] | None) -> None:
    available = set(fieldnames or [])
    missing = sorted(REQUIRED_COLUMNS - available)
    if missing:
        raise CatalogValidationError(f"missing required columns: {', '.join(missing)}")


def row_to_item(row: dict[str, Any]) -> CatalogItem:
    payload: dict[str, Any] = {}
    for column in PAYLOAD_COLUMNS:
        payload[column] = clean_cell(row.get(column))

    unit_price = parse_unit_price(row.get("unit_price"))
    payload["unit_price"] = unit_price
    service_type = classify_service_type(row)
    unit_kind = classify_unit_kind(row.get("unit"))
    payload["service_type"] = service_type
    payload["city_normalized"] = normalize_city(row.get("supplier_city"))
    payload["supplier_status_normalized"] = normalize_status(row.get("supplier_status"))
    payload["unit_kind"] = unit_kind
    payload["quantity_kind"] = classify_quantity_kind(service_type, unit_kind)

    item_id = clean_cell(row.get("id"))
    if not item_id:
        raise CatalogValidationError("row id is required")

    embedding_text = build_embedding_text(row)
    if not embedding_text:
        raise CatalogValidationError(f"row {item_id} has empty embedding text")
    vector = parse_embedding(row.get("embedding"))

    return CatalogItem(
        id=item_id,
        embedding_text=embedding_text,
        vector=vector,
        payload=payload,
        unit_price=unit_price,
    )


def parse_catalog_csv(content: bytes) -> list[CatalogItem]:
    text = content.decode("utf-8-sig")
    reader = csv.DictReader(io.StringIO(text))
    validate_columns(reader.fieldnames)

    items: list[CatalogItem] = []
    for row in reader:
        if not any(clean_cell(value) for value in row.values()):
            continue
        items.append(row_to_item(row))

    if not items:
        raise CatalogValidationError("catalog contains no data rows")
    vector_size = len(items[0].vector)
    for item in items:
        if len(item.vector) != vector_size:
            raise CatalogValidationError(
                f"row {item.id} embedding dimension {len(item.vector)} does not match {vector_size}"
            )
    return items
