from __future__ import annotations

from typing import Any

from .brief import BriefState, ChatClient, Searcher, format_conversation_history, run_brief_turn
from .prompts import COMPOSER_SYSTEM_PROMPT
from .router import RouterDecision, RouterSearchRequest, route_message
from .semantic_agent import format_search_message


def _payload(result: dict[str, Any]) -> dict[str, Any]:
    payload = result.get("payload")
    return payload if isinstance(payload, dict) else result


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
    visible_candidates = [
        item
        for need in state.service_needs.values()
        for item in need.candidate_items
    ]
    route = route_message(
        message=message,
        brief_state=state,
        ui_mode=ui_mode,
        chat_client=chat_client,
        visible_candidates=visible_candidates,
    )

    if route.interface_mode == "chat_search" and route.search_requests:
        found_items = _search_catalog_from_route(route, searcher)
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

    result = run_brief_turn(
        state=state,
        message=message,
        searcher=searcher,
        chat_client=chat_client,
    )
    result["route"] = route.model_dump()
    return result
