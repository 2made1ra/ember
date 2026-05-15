from __future__ import annotations

import re
from typing import Any

from .catalog import normalize_city
from .catalog_store import PostgresCatalogStore
from .config import Settings
from .lm_studio import LMStudioClient


DEFAULT_CANDIDATE_LIMIT = 20
KEYWORD_FIELDS = ("name", "category", "section", "source_text", "supplier")
STOP_WORDS = {
    "без",
    "для",
    "или",
    "как",
    "над",
    "под",
    "при",
    "про",
    "что",
    "это",
}


def _tokens(text: str) -> set[str]:
    return {
        token
        for token in re.findall(r"[0-9A-Za-zА-Яа-яЁё]+", text.lower())
        if len(token) >= 3 and not token.isdigit() and token not in STOP_WORDS
    }


def _payload(result: dict[str, Any]) -> dict[str, Any]:
    payload = result.get("payload")
    return payload if isinstance(payload, dict) else {}


def _keyword_boost(query_terms: set[str], result: dict[str, Any]) -> float:
    if not query_terms:
        return 0.0

    payload = _payload(result)
    boost = 0.0
    field_weights = {
        "name": 0.22,
        "section": 0.18,
        "category": 0.14,
        "source_text": 0.08,
        "supplier": 0.04,
    }

    for field in KEYWORD_FIELDS:
        value = str(payload.get(field) or "").lower()
        if not value:
            continue
        matched = query_terms & _tokens(value)
        if matched:
            boost += field_weights[field] * len(matched)

    return boost


def rerank_results(query: str, results: list[dict[str, Any]], limit: int) -> list[dict[str, Any]]:
    query_terms = _tokens(query)

    def rank_key(indexed_result: tuple[int, dict[str, Any]]) -> tuple[float, float, int]:
        index, result = indexed_result
        semantic_score = float(result.get("score") or 0)
        hybrid_score = semantic_score + _keyword_boost(query_terms, result)
        return hybrid_score, semantic_score, -index

    ranked = sorted(enumerate(results), key=rank_key, reverse=True)
    return [result for _, result in ranked[:limit]]


class PriceSearcher:
    def __init__(self, settings: Settings):
        self.lm = LMStudioClient(settings)
        self.store = PostgresCatalogStore(settings)

    def search(
        self,
        query: str,
        limit: int = 8,
        filters: dict[str, Any] | None = None,
    ) -> list[dict[str, Any]]:
        vector = self.lm.embed([query])[0]
        candidate_limit = max(DEFAULT_CANDIDATE_LIMIT, limit)
        normalized_filters = dict(filters or {})
        if normalized_filters.get("city"):
            normalized_filters["city"] = normalize_city(normalized_filters["city"])
        candidates = self.store.search(vector, limit=candidate_limit, filters=normalized_filters or None)
        return rerank_results(query, candidates, limit)
