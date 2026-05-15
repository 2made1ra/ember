from __future__ import annotations

import json
import re
from typing import Any, Literal, Protocol

from pydantic import BaseModel, ConfigDict, Field

from .brief import BriefState
from .catalog import normalize_city
from .prompts import ROUTER_SYSTEM_PROMPT


class ChatClient(Protocol):
    def complete(self, system: str, user: str) -> str:
        ...


InterfaceMode = Literal["chat_search", "brief_workspace"]
Intent = Literal[
    "clarification",
    "supplier_search",
    "brief_discovery",
    "mixed",
    "verification",
    "selection",
    "comparison",
    "render_brief",
]
WorkflowStage = Literal[
    "clarifying",
    "searching",
    "supplier_searching",
    "supplier_verification",
    "search_results_shown",
    "brief_rendered",
]


class RouterFilters(BaseModel):
    model_config = ConfigDict(extra="forbid")

    supplier_city_normalized: str | None = None
    category: str | None = None
    supplier_status_normalized: str | None = None
    has_vat: str | None = None
    vat_mode: str | None = None
    unit_price_min: float | None = None
    unit_price_max: float | None = None


class RouterSearchRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    query: str
    service_category: str = ""
    filters: RouterFilters = Field(default_factory=RouterFilters)
    priority: int = Field(default=1, ge=1)
    limit: int = Field(default=8, ge=1, le=20)


class RouterDecision(BaseModel):
    model_config = ConfigDict(extra="forbid")

    interface_mode: InterfaceMode
    intent: Intent
    workflow_stage: WorkflowStage
    confidence: float = Field(ge=0, le=1)
    reason_codes: list[str] = Field(default_factory=list)
    brief_update: dict[str, Any] = Field(default_factory=dict)
    search_requests: list[RouterSearchRequest] = Field(default_factory=list)
    tool_intents: list[str] = Field(default_factory=list)
    missing_fields: list[str] = Field(default_factory=list)
    clarification_questions: list[str] = Field(default_factory=list)


SEARCH_WORDS = (
    "найди",
    "найти",
    "покажи",
    "подбери",
    "есть",
    "подрядчик",
    "подрядчиков",
    "поставщик",
    "поставщика",
    "цена",
    "цену",
    "инн",
)

SEARCH_STOP_WORDS = (
    "найди",
    "найти",
    "покажи",
    "подбери",
    "мне",
    "нужно",
    "нужен",
    "нужна",
    "есть",
    "подрядчиков",
    "подрядчика",
    "поставщиков",
    "поставщика",
    "поставщик",
    "цена",
    "цену",
)

RENDER_BRIEF_WORDS = (
    "бриф",
    "черновик",
    "структур",
    "итог",
    "финал",
    "результат",
)

RENDER_ACTION_WORDS = (
    "покажи",
    "показать",
    "выведи",
    "вывести",
    "отобрази",
    "дай",
    "собери",
    "сформируй",
    "составь",
)

SELECTION_WORDS = (
    "выбери",
    "выбрать",
    "выбираю",
    "добавь",
    "добавить",
    "оставь",
    "оставить",
    "берем",
    "берём",
    "зафиксируй",
    "select",
)

SELECTION_ID_PATTERN = re.compile(
    r"(?:\b(?:id|ид)\s*[:#№-]?\s*|#)([0-9a-zа-яё_-]+)",
    re.IGNORECASE,
)

CATEGORY_TERMS = {
    "звук": ("микроф", "радиомикроф", "звук", "акустик", "микшер"),
    "свет": ("свет", "прожектор", "beam", "wash", "led"),
    "кейтеринг": ("кейтер", "фуршет", "кофе", "еда", "питан", "обед", "ужин"),
    "площадка": ("площад", "зал", "лофт", "venue"),
    "мебель": ("мебел", "стол", "стул", "стойка"),
    "спортивный инвентарь": ("спортинвент", "спортив"),
}

QUERY_NORMALIZATIONS = (
    (re.compile(r"\bрадиомикрофон\w*\b", re.IGNORECASE), "радиомикрофон"),
    (re.compile(r"\bмикрофон\w*\b", re.IGNORECASE), "микрофон"),
)

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


def parse_router_decision(raw: str) -> RouterDecision:
    text = raw.strip()
    if text.startswith("```"):
        text = re.sub(r"^```(?:json)?\s*", "", text)
        text = re.sub(r"\s*```$", "", text)
    return RouterDecision.model_validate(json.loads(text))


def build_router_prompt(
    message: str,
    brief_state: BriefState,
    visible_candidates: list[dict[str, Any]] | None = None,
    ui_mode: str = "brief",
) -> str:
    payload = {
        "message": message,
        "brief_state": brief_state.to_dict(),
        "visible_candidates": visible_candidates or [],
    }
    return (
        f"ui_mode={ui_mode}\n"
        "Разбери пользовательское сообщение и верни только JSON по schema из system prompt.\n"
        f"input={json.dumps(payload, ensure_ascii=False)}"
    )


def _detect_city(lowered: str) -> str | None:
    for alias, normalized in CITY_ALIASES.items():
        if alias in lowered:
            return normalized
    city_match = re.search(r"(?:в городе|город|в)\s+([а-яёa-z-]+)", lowered)
    if city_match:
        return normalize_city(city_match.group(1))
    return None


def _detect_category(lowered: str) -> str:
    for category, needles in CATEGORY_TERMS.items():
        if any(needle in lowered for needle in needles):
            return category
    return ""


def _extract_price_max(lowered: str) -> float | None:
    match = re.search(r"\bдо\s+(\d[\d\s]*)", lowered)
    if not match:
        return None
    return float(match.group(1).replace(" ", ""))


def _semantic_query(message: str, category: str) -> str:
    lowered = message.lower().replace("ё", "е")
    for pattern, replacement in QUERY_NORMALIZATIONS:
        if pattern.search(lowered):
            return replacement

    tokens = [
        token
        for token in re.findall(r"[0-9a-zа-яё-]+", lowered)
        if token not in SEARCH_STOP_WORDS
        and not token.isdigit()
        and token not in CITY_ALIASES
        and len(token) > 2
    ]
    if category:
        return category
    return " ".join(tokens[:4]).strip() or message.strip()


def _search_decision(message: str, brief_state: BriefState, confidence: float = 0.72) -> RouterDecision:
    lowered = message.lower().replace("ё", "е")
    category = _detect_category(lowered)
    filters = RouterFilters(
        supplier_city_normalized=_detect_city(lowered),
        vat_mode="without_vat" if "без ндс" in lowered else "with_vat" if "с ндс" in lowered else None,
        has_vat="Без НДС" if "без ндс" in lowered else None,
        unit_price_max=_extract_price_max(lowered),
    )
    request = RouterSearchRequest(
        query=_semantic_query(message, category),
        service_category=category,
        filters=filters,
        priority=1,
        limit=8,
    )
    return RouterDecision(
        interface_mode="chat_search",
        intent="supplier_search",
        workflow_stage="searching",
        confidence=confidence,
        reason_codes=["catalog_search"],
        brief_update={},
        search_requests=[request],
        tool_intents=["search_items"],
        missing_fields=[],
        clarification_questions=[],
    )


def _looks_like_selection(message: str) -> bool:
    lowered = message.lower().replace("ё", "е")
    return any(word in lowered for word in SELECTION_WORDS) and bool(
        SELECTION_ID_PATTERN.search(message)
    )


def _selection_decision() -> RouterDecision:
    return RouterDecision(
        interface_mode="brief_workspace",
        intent="selection",
        workflow_stage="search_results_shown",
        confidence=0.8,
        reason_codes=["explicit_selection"],
        brief_update={},
        search_requests=[],
        tool_intents=["select_item"],
        missing_fields=[],
        clarification_questions=[],
    )


def _looks_like_render_brief(message: str, brief_state: BriefState) -> bool:
    lowered = message.lower().replace("ё", "е")
    has_render_word = any(word in lowered for word in RENDER_BRIEF_WORDS)
    has_action_word = any(word in lowered for word in RENDER_ACTION_WORDS)
    has_brief_context = bool(
        brief_state.confirmed_requirements
        or brief_state.event_type
        or brief_state.city
        or brief_state.guests_count
        or any(need.candidate_items for need in brief_state.service_needs.values())
        or brief_state.selected_price_items
    )
    return has_render_word and has_action_word and has_brief_context


def _render_brief_decision() -> RouterDecision:
    return RouterDecision(
        interface_mode="brief_workspace",
        intent="render_brief",
        workflow_stage="brief_rendered",
        confidence=0.86,
        reason_codes=["explicit_render_brief"],
        brief_update={},
        search_requests=[],
        tool_intents=["render_event_brief"],
        missing_fields=[],
        clarification_questions=[],
    )


def heuristic_route(message: str, brief_state: BriefState, ui_mode: str = "brief") -> RouterDecision:
    lowered = message.lower().replace("ё", "е")
    if _looks_like_selection(message):
        return _selection_decision()
    if _looks_like_render_brief(message, brief_state):
        return _render_brief_decision()
    if ui_mode == "search" or any(word in lowered for word in SEARCH_WORDS):
        return _search_decision(message, brief_state)

    return RouterDecision(
        interface_mode="brief_workspace",
        intent="brief_discovery",
        workflow_stage="clarifying",
        confidence=0.7,
        reason_codes=["brief_mode"],
        brief_update={},
        search_requests=[],
        tool_intents=["update_brief"],
        missing_fields=[],
        clarification_questions=[],
    )


def should_use_llm_router(message: str, ui_mode: str = "brief") -> bool:
    lowered = message.lower().replace("ё", "е")
    return (
        ui_mode == "search"
        or any(word in lowered for word in SEARCH_WORDS)
        or _looks_like_selection(message)
    )


def route_message(
    message: str,
    brief_state: BriefState,
    ui_mode: str,
    chat_client: ChatClient | None = None,
    visible_candidates: list[dict[str, Any]] | None = None,
) -> RouterDecision:
    if _looks_like_render_brief(message, brief_state):
        return _render_brief_decision()

    if chat_client and should_use_llm_router(message, ui_mode):
        prompt = build_router_prompt(
            message=message,
            brief_state=brief_state,
            visible_candidates=visible_candidates,
            ui_mode=ui_mode,
        )
        try:
            return parse_router_decision(chat_client.complete(ROUTER_SYSTEM_PROMPT, prompt))
        except Exception:
            return heuristic_route(message, brief_state, ui_mode)

    return heuristic_route(message, brief_state, ui_mode)
