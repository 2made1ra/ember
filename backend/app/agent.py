from __future__ import annotations

import re
from typing import Any

from .brief import (
    BriefState,
    ChatClient,
    Searcher,
    budget_lines_from_results,
    default_answer,
    estimate_budget,
    format_conversation_history,
    run_brief_turn,
)
from .prompts import COMPOSER_SYSTEM_PROMPT
from .router import RouterDecision, RouterSearchRequest, route_message
from .semantic_agent import format_search_message


def _payload(result: dict[str, Any]) -> dict[str, Any]:
    payload = result.get("payload")
    return payload if isinstance(payload, dict) else result


def _candidate_item_id(item: dict[str, Any]) -> str:
    payload = _payload(item)
    return str(payload.get("id") or item.get("id") or "").strip()


def _selection_ids_from_message(message: str) -> list[str]:
    ids = re.findall(
        r"(?:\b(?:id|ид)\s*[:#№-]?\s*|#)([0-9a-zа-яё_-]+)",
        message,
        flags=re.IGNORECASE,
    )
    return [item_id.strip() for item_id in ids if item_id.strip()]


def _selection_ids_from_route(route: RouterDecision) -> list[str]:
    brief_update = route.brief_update if isinstance(route.brief_update, dict) else {}
    raw_values: list[Any] = []
    for key in ("item_id", "selected_item_id"):
        raw_values.append(brief_update.get(key))
    for key in ("item_ids", "selected_item_ids"):
        value = brief_update.get(key)
        if isinstance(value, list):
            raw_values.extend(value)
        else:
            raw_values.append(value)
    return [str(value).strip() for value in raw_values if str(value or "").strip()]


def _ordered_unique(values: list[str]) -> list[str]:
    seen: set[str] = set()
    result: list[str] = []
    for value in values:
        if value in seen:
            continue
        seen.add(value)
        result.append(value)
    return result


def _visible_candidates_from_state(state: BriefState) -> list[dict[str, Any]]:
    visible_candidates: list[dict[str, Any]] = []
    seen_ids: set[str] = set()
    for need in state.service_needs.values():
        for item in need.candidate_items:
            item_id = _candidate_item_id(item)
            if item_id and item_id in seen_ids:
                continue
            if item_id:
                seen_ids.add(item_id)
            visible_candidates.append(item)

    for item in state.last_visible_search_candidates:
        item_id = _candidate_item_id(item)
        if item_id and item_id in seen_ids:
            continue
        if item_id:
            seen_ids.add(item_id)
        visible_candidates.append(item)
    return visible_candidates


def _select_visible_items(
    *,
    state: BriefState,
    message: str,
    route: RouterDecision,
    visible_candidates: list[dict[str, Any]],
) -> list[str]:
    if route.intent != "selection" and "select_item" not in route.tool_intents:
        return []

    requested_ids = _ordered_unique(
        _selection_ids_from_route(route) + _selection_ids_from_message(message)
    )
    if not requested_ids:
        return []

    selected_ids: list[str] = []
    visible_by_id = {
        item_id: item
        for item in visible_candidates
        if (item_id := _candidate_item_id(item))
    }
    persisted_ids = {
        item_id
        for need in state.service_needs.values()
        for item in need.candidate_items
        if (item_id := _candidate_item_id(item))
    }

    for item_id in requested_ids:
        matched_persisted_candidate = False
        for need in state.service_needs.values():
            if item_id not in {_candidate_item_id(item) for item in need.candidate_items}:
                continue
            matched_persisted_candidate = True
            if item_id not in need.selected_item_ids:
                need.selected_item_ids.append(item_id)
            if item_id not in selected_ids:
                selected_ids.append(item_id)

        if matched_persisted_candidate or item_id not in visible_by_id or item_id in persisted_ids:
            continue

        if not any(_candidate_item_id(item) == item_id for item in state.selected_price_items):
            state.selected_price_items.append(visible_by_id[item_id])
        selected_ids.append(item_id)

    return selected_ids


def _items_for_ids(
    item_ids: list[str],
    visible_candidates: list[dict[str, Any]],
) -> list[dict[str, Any]]:
    requested_ids = set(item_ids)
    items: list[dict[str, Any]] = []
    seen_ids: set[str] = set()
    for item in visible_candidates:
        item_id = _candidate_item_id(item)
        if item_id not in requested_ids or item_id in seen_ids:
            continue
        seen_ids.add(item_id)
        items.append(item)
    return items


def _format_money(value: Any) -> str:
    try:
        amount = float(value)
    except (TypeError, ValueError):
        return "цена не указана"
    if amount.is_integer():
        return f"{int(amount):,}".replace(",", " ") + " ₽"
    return f"{amount:,.2f}".replace(",", " ").replace(".", ",") + " ₽"


def _compose_selection_answer(selected_ids: list[str], budget: dict[str, Any]) -> str:
    if not selected_ids:
        return (
            "Не нашел указанные ID среди видимых кандидатов. "
            "Выберите ID из короткого списка, "
            "который уже показан в брифе."
        )

    parts = [
        "Выбрал позиции: "
        + ", ".join(f"ID {item_id}" for item_id in selected_ids)
        + "."
    ]
    if budget["lines"]:
        total = _format_money(budget["total"])
        parts.append(f"\nОриентировочная смета по выбранным позициям: {total}")
        for line in budget["lines"]:
            parts.append(
                f"- {line['name']}: {_format_money(line['unit_price'])} × "
                f"{line['quantity']:g} = {_format_money(line['subtotal'])}"
            )
    return "\n".join(parts)


def _search_filters(request: RouterSearchRequest) -> dict[str, Any]:
    filters: dict[str, Any] = {}
    if request.filters.supplier_city_normalized:
        filters["city"] = request.filters.supplier_city_normalized
    if request.filters.supplier_status_normalized == "активен":
        filters["only_active"] = True
    return filters


def _matches_numeric_filters(item: dict[str, Any], request: RouterSearchRequest) -> bool:
    payload = _payload(item)
    try:
        unit_price = float(payload.get("unit_price") or 0)
    except (TypeError, ValueError):
        return False

    if request.filters.unit_price_min is not None and unit_price < request.filters.unit_price_min:
        return False
    if request.filters.unit_price_max is not None and unit_price > request.filters.unit_price_max:
        return False
    return True


def _search_catalog_from_route(
    route: RouterDecision,
    searcher: Searcher,
) -> list[dict[str, Any]]:
    found_items: list[dict[str, Any]] = []
    seen_ids: set[str] = set()
    for request in sorted(route.search_requests, key=lambda item: item.priority):
        filters = _search_filters(request)
        items = searcher.search(request.query, limit=request.limit, filters=filters or None)
        for item in items:
            if not _matches_numeric_filters(item, request):
                continue
            item_id = str(_payload(item).get("id") or "")
            if item_id and item_id in seen_ids:
                continue
            if item_id:
                seen_ids.add(item_id)
            found_items.append(item)
    return found_items


def _compose_search_answer(
    *,
    state: BriefState,
    message: str,
    found_items: list[dict[str, Any]],
    route: RouterDecision,
    chat_client: ChatClient | None,
) -> str:
    if found_items:
        fallback = (
            "Нашел варианты в каталоге. Это предварительные кандидаты, они еще не выбраны в бриф.\n"
            + format_search_message(message, found_items[:5])
            + "\n\nДальше можно уточнить фильтр, выбрать позиции по ID или проверить поставщика."
        )
    else:
        fallback = (
            "В каталоге нет подходящих строк по текущему запросу и фильтрам. "
            "Можно расширить запрос или убрать часть ограничений."
        )

    if not chat_client:
        return fallback

    prompt = (
        "Сформулируй короткий ответ менеджеру на русском по результатам backend tools.\n\n"
        "ui_mode=chat_search\n"
        f"История текущего диалога:\n{format_conversation_history(state.conversation_history)}\n\n"
        f"Текущий запрос пользователя:\n{message}\n\n"
        f"route={route.model_dump()}\n"
        f"brief={state.to_dict()}\n"
        f"found_items={found_items[:10]}\n"
        "item_details=[]\n"
        "verification_results=[]\n"
        "budget={'lines': [], 'total': 0}\n\n"
        f"Черновик ответа:\n{fallback}"
    )
    try:
        return chat_client.complete(COMPOSER_SYSTEM_PROMPT, prompt)
    except Exception:
        return fallback


def run_argus_turn(
    *,
    state: BriefState,
    message: str,
    searcher: Searcher,
    chat_client: ChatClient | None = None,
    ui_mode: str = "brief",
) -> dict[str, Any]:
    visible_candidates = _visible_candidates_from_state(state)
    route = route_message(
        message=message,
        brief_state=state,
        ui_mode=ui_mode,
        chat_client=chat_client,
        visible_candidates=visible_candidates,
    )
    selected_ids = _select_visible_items(
        state=state,
        message=message,
        route=route,
        visible_candidates=visible_candidates,
    )

    if route.intent == "selection" or "select_item" in route.tool_intents:
        selected_items = _items_for_ids(selected_ids, visible_candidates)
        budget = estimate_budget(budget_lines_from_results(selected_items, state))
        answer = _compose_selection_answer(selected_ids, budget)
        state.conversation_history.append({"role": "user", "content": message})
        state.conversation_history.append({"role": "assistant", "content": answer})
        return {
            "message": answer,
            "brief_state": state.to_dict(),
            "found_items": selected_items[:10],
            "items": selected_items[:10],
            "budget": budget,
            "route": route.model_dump(),
        }

    if route.interface_mode == "chat_search" and route.search_requests:
        found_items = _search_catalog_from_route(route, searcher)
        state.last_visible_search_candidates = found_items[:10]
        answer = _compose_search_answer(
            state=state,
            message=message,
            found_items=found_items,
            route=route,
            chat_client=chat_client,
        )
        state.conversation_history.append({"role": "user", "content": message})
        state.conversation_history.append({"role": "assistant", "content": answer})
        return {
            "message": answer,
            "brief_state": state.to_dict(),
            "found_items": found_items[:10],
            "items": found_items[:10],
            "budget": {"lines": [], "total": 0},
            "route": route.model_dump(),
        }

    if route.intent == "render_brief" or "render_event_brief" in route.tool_intents:
        found_items = visible_candidates[:10]
        budget = estimate_budget(budget_lines_from_results(found_items, state))
        state.stage = "brief_rendered"
        answer = default_answer(state, found_items, budget)
        state.conversation_history.append({"role": "user", "content": message})
        state.conversation_history.append({"role": "assistant", "content": answer})
        return {
            "message": answer,
            "brief_state": state.to_dict(),
            "found_items": found_items,
            "items": found_items,
            "budget": budget,
            "route": route.model_dump(),
        }

    result = run_brief_turn(
        state=state,
        message=message,
        searcher=searcher,
        chat_client=chat_client,
    )
    result["route"] = route.model_dump()
    return result
