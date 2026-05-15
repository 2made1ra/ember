from __future__ import annotations

from typing import Any, Protocol, TypedDict

try:
    from langchain_core.tools import StructuredTool
    from langgraph.graph import END, StateGraph
except ImportError:  # pragma: no cover - local tests can run before optional deps are installed.
    StructuredTool = None
    END = "__end__"
    StateGraph = None


class Searcher(Protocol):
    def search(self, query: str, limit: int = 8) -> list[dict[str, Any]]:
        ...


class SemanticSearchState(TypedDict, total=False):
    query: str
    limit: int
    items: list[dict[str, Any]]
    message: str


def _clean(value: Any, fallback: str = "") -> str:
    text = str(value or "").strip()
    return text or fallback


def _format_money(value: Any) -> str:
    try:
        amount = float(value)
    except (TypeError, ValueError):
        return "цена не указана"
    if amount.is_integer():
        return f"{int(amount):,}".replace(",", " ") + " ₽"
    return f"{amount:,.2f}".replace(",", " ").replace(".", ",") + " ₽"


def _payload(result: dict[str, Any]) -> dict[str, Any]:
    payload = result.get("payload")
    return payload if isinstance(payload, dict) else result


def format_price_item(item: dict[str, Any], index: int) -> str:
    payload = _payload(item)
    name = _clean(payload.get("name"), "Позиция без названия")
    unit = _clean(payload.get("unit"), "ед.")
    supplier = _clean(payload.get("supplier"), "поставщик не указан")
    city = _clean(payload.get("supplier_city"))
    category = _clean(payload.get("category"))
    section = _clean(payload.get("section"))
    item_id = _clean(payload.get("id"), "не указан")

    supplier_text = supplier if not city else f"{supplier}, {city}"
    category_parts = [part for part in [category, section] if part]
    category_text = f" Категория: {' / '.join(category_parts)}." if category_parts else ""

    return (
        f"{index}. {name} — {_format_money(payload.get('unit_price'))} за {unit}. "
        f"Поставщик: {supplier_text}."
        f"{category_text} ID {item_id}."
    )


def format_search_message(query: str, items: list[dict[str, Any]]) -> str:
    if not items:
        return "Ничего не найдено. Попробуйте уточнить услугу, формат или категорию."

    return "\n".join(format_price_item(item, index) for index, item in enumerate(items[:3], start=1))


def _search_with_tool(searcher: Searcher, query: str, limit: int) -> list[dict[str, Any]]:
    if StructuredTool is None:
        return searcher.search(query, limit=limit)

    def search_price_catalog(query: str, limit: int = 3) -> list[dict[str, Any]]:
        """Find price catalog rows by semantic similarity."""
        return searcher.search(query, limit=limit)

    tool = StructuredTool.from_function(search_price_catalog)
    result = tool.invoke({"query": query, "limit": limit})
    return list(result)


def run_semantic_search_agent(query: str, searcher: Searcher, limit: int = 3) -> dict[str, Any]:
    initial_state: SemanticSearchState = {"query": query, "limit": limit, "items": [], "message": ""}

    def search_node(state: SemanticSearchState) -> SemanticSearchState:
        items = _search_with_tool(searcher, state["query"], int(state.get("limit") or 3))
        return {"items": items[:limit]}

    def format_node(state: SemanticSearchState) -> SemanticSearchState:
        return {"message": format_search_message(state["query"], state.get("items", []))}

    if StateGraph is None:
        state = {**initial_state, **search_node(initial_state)}
        state = {**state, **format_node(state)}
        return {"message": state["message"], "items": state["items"]}

    graph = StateGraph(SemanticSearchState)
    graph.add_node("search_catalog", search_node)
    graph.add_node("format_response", format_node)
    graph.set_entry_point("search_catalog")
    graph.add_edge("search_catalog", "format_response")
    graph.add_edge("format_response", END)
    result = graph.compile().invoke(initial_state)
    return {"message": result["message"], "items": result.get("items", [])}
