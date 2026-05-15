from __future__ import annotations

import json
import re
from dataclasses import dataclass
from typing import Any

from .catalog import normalize_city
from .catalog_store import PostgresCatalogStore
from .config import Settings
from .errors import DependencyUnavailableError
from .lm_studio import LMStudioClient
from .prompts import RERANKER_SYSTEM_PROMPT


DEFAULT_CANDIDATE_LIMIT = 80
LLM_RERANK_LIMIT = 20
RRF_K = 60
SEMANTIC_RRF_WEIGHT = 1.0
LEXICAL_RRF_WEIGHT = 1.25
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
CITY_ALIASES = {
    "екб": "екатеринбург",
    "екат": "екатеринбург",
    "екатеринбурге": "екатеринбург",
    "екатеринбург": "екатеринбург",
    "москве": "москва",
    "москва": "москва",
    "санкт-петербурге": "санкт-петербург",
    "санкт-петербург": "санкт-петербург",
}
TOKEN_RE = re.compile(r"[0-9A-Za-zА-Яа-яЁё]+")
DATE_RE = re.compile(r"\b\d{1,2}[./-]\d{1,2}(?:[./-]\d{2,4})?\b")
NUMBER_RE = re.compile(r"\b\d+(?:[.,]\d+)?\b")


@dataclass(frozen=True)
class SearchQueryFeatures:
    phrase: str
    tokens: tuple[str, ...]
    token_set: frozenset[str]
    numbers: frozenset[str]
    ngrams: tuple[str, ...]
    cities: frozenset[str]


def _normalize_text(text: str) -> str:
    lowered = str(text or "").lower().replace("ё", "е")
    return re.sub(r"\s+", " ", lowered).strip()


def _tokens(text: str) -> set[str]:
    return set(_ordered_tokens(text))


def _ordered_tokens(text: str) -> tuple[str, ...]:
    normalized = _normalize_text(text)
    return tuple(
        token
        for token in TOKEN_RE.findall(normalized)
        if len(token) >= 3 and not token.isdigit() and token not in STOP_WORDS
    )


def _numbers(text: str) -> frozenset[str]:
    normalized = _normalize_text(text)
    values = set(DATE_RE.findall(normalized))
    values.update(NUMBER_RE.findall(normalized))
    return frozenset(values)


def _ngrams(tokens: tuple[str, ...]) -> tuple[str, ...]:
    grams: list[str] = []
    for size in (2, 3):
        for index in range(0, len(tokens) - size + 1):
            grams.append(" ".join(tokens[index : index + size]))
    return tuple(grams)


def _cities(text: str) -> frozenset[str]:
    normalized = _normalize_text(text)
    found = {
        normalized_city
        for alias, normalized_city in CITY_ALIASES.items()
        if re.search(rf"(?<![0-9a-zа-яё]){re.escape(alias)}(?![0-9a-zа-яё])", normalized)
    }
    city_match = re.search(r"(?:в городе|город|в)\s+([а-яёa-z-]+)", normalized)
    if city_match:
        found.add(normalize_city(city_match.group(1)))
    return frozenset(found)


def analyze_query(query: str) -> SearchQueryFeatures:
    tokens = _ordered_tokens(query)
    return SearchQueryFeatures(
        phrase=_normalize_text(query),
        tokens=tokens,
        token_set=frozenset(tokens),
        numbers=_numbers(query),
        ngrams=_ngrams(tokens),
        cities=_cities(query),
    )


def _payload(result: dict[str, Any]) -> dict[str, Any]:
    payload = result.get("payload")
    return payload if isinstance(payload, dict) else {}


def _result_id(result: dict[str, Any], fallback: str) -> str:
    item_id = str(_payload(result).get("id") or "").strip()
    return item_id or fallback


def _field_text(payload: dict[str, Any], field: str) -> str:
    return _normalize_text(str(payload.get(field) or ""))


def _combined_text(payload: dict[str, Any]) -> str:
    values = [
        payload.get("name"),
        payload.get("category"),
        payload.get("section"),
        payload.get("source_text"),
        payload.get("supplier"),
        payload.get("supplier_city"),
        payload.get("supplier_inn"),
    ]
    return _normalize_text(" ".join(str(value or "") for value in values))


def _document_frequencies(
    features: SearchQueryFeatures,
    results: list[dict[str, Any]],
) -> dict[str, int]:
    frequencies = {token: 0 for token in features.token_set}
    for result in results:
        document_tokens = _tokens(_combined_text(_payload(result)))
        for token in features.token_set & document_tokens:
            frequencies[token] += 1
    return frequencies


def _keyword_boost(features: SearchQueryFeatures, result: dict[str, Any]) -> float:
    if not features.token_set:
        return 0.0

    payload = _payload(result)
    boost = 0.0
    field_weights = {
        "name": 0.08,
        "section": 0.05,
        "category": 0.05,
        "source_text": 0.07,
        "supplier": 0.02,
    }

    for field in KEYWORD_FIELDS:
        matched = features.token_set & _tokens(str(payload.get(field) or ""))
        if matched:
            boost += field_weights[field] * len(matched)

    return boost


def _deterministic_boost(
    features: SearchQueryFeatures,
    result: dict[str, Any],
    frequencies: dict[str, int],
    total_candidates: int,
) -> float:
    payload = _payload(result)
    boost = _keyword_boost(features, result)
    source_text = _field_text(payload, "source_text")
    name_text = _field_text(payload, "name")
    combined_text = _combined_text(payload)

    if len(features.phrase) >= 4 and (features.phrase in source_text or features.phrase in name_text):
        boost += 0.55

    result_numbers = _numbers(combined_text)
    if features.numbers and result_numbers:
        boost += 0.12 * len(features.numbers & result_numbers)

    if features.cities:
        payload_cities = {
            normalize_city(str(payload.get("supplier_city") or "")),
            normalize_city(str(payload.get("city_normalized") or "")),
        }
        if features.cities & payload_cities:
            boost += 0.2

    document_tokens = _tokens(combined_text)
    rare_threshold = max(1, total_candidates // 4)
    for token in features.token_set & document_tokens:
        if frequencies.get(token, 0) <= rare_threshold:
            boost += 0.06

    token_text = " ".join(TOKEN_RE.findall(combined_text))
    for ngram in features.ngrams:
        if ngram in token_text:
            boost += 0.08

    return boost


def _merge_candidates(
    *,
    semantic_results: list[dict[str, Any]],
    lexical_results: list[dict[str, Any]],
    features: SearchQueryFeatures,
) -> list[dict[str, Any]]:
    merged: dict[str, dict[str, Any]] = {}

    def add_results(results: list[dict[str, Any]], weight: float, channel: str) -> None:
        for rank, result in enumerate(results, start=1):
            item_id = _result_id(result, f"{channel}:{rank}")
            entry = merged.setdefault(
                item_id,
                {
                    "result": dict(result),
                    "score": 0.0,
                },
            )
            entry["score"] += weight / (rank + RRF_K)

    add_results(semantic_results, SEMANTIC_RRF_WEIGHT, "semantic")
    add_results(lexical_results, LEXICAL_RRF_WEIGHT, "lexical")

    candidates = [entry["result"] for entry in merged.values()]
    frequencies = _document_frequencies(features, candidates)
    total_candidates = len(candidates)
    ranked: list[dict[str, Any]] = []
    for item_id, entry in merged.items():
        result = dict(entry["result"])
        score = float(entry["score"]) + _deterministic_boost(
            features,
            result,
            frequencies,
            total_candidates,
        )
        result["score"] = score
        result["_hybrid_id"] = item_id
        ranked.append(result)

    return sorted(ranked, key=lambda result: float(result.get("score") or 0), reverse=True)


def _compact_candidate(result: dict[str, Any]) -> dict[str, Any]:
    payload = _payload(result)
    source_text = str(payload.get("source_text") or "")
    if len(source_text) > 500:
        source_text = source_text[:500]
    return {
        "id": payload.get("id"),
        "name": payload.get("name"),
        "category": payload.get("category"),
        "section": payload.get("section"),
        "unit": payload.get("unit"),
        "unit_price": payload.get("unit_price"),
        "source_text": source_text,
        "supplier": payload.get("supplier"),
        "city": payload.get("supplier_city") or payload.get("city_normalized"),
        "status": payload.get("supplier_status") or payload.get("supplier_status_normalized"),
        "hybrid_score": result.get("score"),
    }


def _rerank_prompt(query: str, filters: dict[str, Any], candidates: list[dict[str, Any]]) -> str:
    payload = {
        "query": query,
        "filters": filters,
        "candidates": [_compact_candidate(result) for result in candidates],
        "expected_output": {"items": [{"id": "string", "score": 0.0, "reason": "string"}]},
    }
    return (
        "Оцени релевантность candidate rows запросу и верни только JSON указанной формы.\n"
        f"{json.dumps(payload, ensure_ascii=False)}"
    )


def _strip_json_fence(raw: str) -> str:
    text = raw.strip()
    if text.startswith("```"):
        text = re.sub(r"^```(?:json)?\s*", "", text)
        text = re.sub(r"\s*```$", "", text)
    return text


def _parse_llm_scores(raw: str, known_ids: set[str]) -> dict[str, float]:
    try:
        payload = json.loads(_strip_json_fence(raw))
    except json.JSONDecodeError as exc:
        raise ValueError("LLM rerank returned invalid JSON") from exc
    if not isinstance(payload, dict) or not isinstance(payload.get("items"), list):
        raise ValueError("LLM rerank returned invalid shape")

    scores: dict[str, float] = {}
    for item in payload["items"]:
        if not isinstance(item, dict):
            continue
        item_id = str(item.get("id") or "").strip()
        if item_id not in known_ids:
            continue
        try:
            score = float(item.get("score"))
        except (TypeError, ValueError):
            continue
        scores[item_id] = min(1.0, max(0.0, score))
    return scores


def _llm_rerank(
    *,
    lm: LMStudioClient,
    query: str,
    filters: dict[str, Any],
    candidates: list[dict[str, Any]],
    limit: int,
) -> list[dict[str, Any]]:
    top_candidates = candidates[:LLM_RERANK_LIMIT]
    if not top_candidates:
        return []

    known_ids = {
        item_id
        for result in top_candidates
        if (item_id := str(_payload(result).get("id") or "").strip())
    }
    try:
        raw = lm.complete(RERANKER_SYSTEM_PROMPT, _rerank_prompt(query, filters, top_candidates))
        llm_scores = _parse_llm_scores(raw, known_ids)
    except Exception as exc:
        raise DependencyUnavailableError(
            "LLM rerank недоступен: не удалось переоценить кандидатов поиска."
        ) from exc

    def rank_key(indexed_result: tuple[int, dict[str, Any]]) -> tuple[float, float, int]:
        index, result = indexed_result
        item_id = str(_payload(result).get("id") or "").strip()
        return llm_scores.get(item_id, 0.0), float(result.get("score") or 0), -index

    ranked = sorted(enumerate(top_candidates), key=rank_key, reverse=True)
    results: list[dict[str, Any]] = []
    for _, result in ranked[:limit]:
        public_result = dict(result)
        public_result.pop("_hybrid_id", None)
        results.append(public_result)
    return results


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
        search_filters = normalized_filters or None
        semantic_candidates = self.store.search(
            vector,
            limit=candidate_limit,
            filters=search_filters,
        )
        lexical_candidates = self.store.lexical_search(
            query,
            limit=candidate_limit,
            filters=search_filters,
        )
        features = analyze_query(query)
        candidates = _merge_candidates(
            semantic_results=semantic_candidates,
            lexical_results=lexical_candidates,
            features=features,
        )
        return _llm_rerank(
            lm=self.lm,
            query=query,
            filters=normalized_filters,
            candidates=candidates,
            limit=limit,
        )
