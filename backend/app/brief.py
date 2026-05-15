from __future__ import annotations

import re
from dataclasses import dataclass, field
from typing import Any, Protocol, TypedDict

from .catalog import normalize_city
from .prompts import COMPOSER_SYSTEM_PROMPT

try:
    from langgraph.graph import END, StateGraph
except ImportError:  # pragma: no cover - tests can run before optional deps are installed.
    END = "__end__"
    StateGraph = None


class Searcher(Protocol):
    def search(
        self,
        query: str,
        limit: int = 8,
        filters: dict[str, Any] | None = None,
    ) -> list[dict[str, Any]]:
        ...


class ChatClient(Protocol):
    def complete(self, system: str, user: str) -> str:
        ...


SERVICE_LABELS = {
    "venue": "Площадка",
    "catering": "Питание",
    "av_equipment": "Оборудование и AV",
    "staff": "Персонал",
    "transport": "Транспорт",
    "accommodation": "Проживание",
    "branding": "Брендинг и навигация",
    "print": "Полиграфия",
    "merch": "Сувениры",
    "entertainment": "Программа",
    "security": "Безопасность",
}

SERVICE_KEYWORDS = {
    "venue": ["площад", "зал", "помещен", "конференц-зал", "аренд"],
    "catering": ["питан", "кофе", "обед", "ужин", "фуршет", "кейтер", "напит", "банкет"],
    "av_equipment": ["звук", "свет", "экран", "микроф", "трансляц", "оборуд", "проектор"],
    "staff": ["персонал", "регистрац", "хостес", "волонтер", "волонтёр", "техник"],
    "transport": ["трансфер", "транспорт", "автобус", "перевоз", "логист"],
    "accommodation": ["прожив", "гостиниц", "отель", "номер"],
    "branding": ["бренд", "баннер", "стенд", "навигац", "оформлен"],
    "print": ["полиграф", "печать", "буклет", "бейдж", "плакат"],
    "merch": ["сувен", "мерч", "подар"],
    "entertainment": ["ведущ", "артист", "шоу", "развлекатель", "музык"],
    "security": ["безопас", "охран", "досмотр"],
}

SERVICE_QUERIES = {
    "venue": "аренда площадки конференц зал",
    "catering": "кофе-брейк обед ужин кейтеринг питание",
    "av_equipment": "звук свет экран радиомикрофон техническое оборудование",
    "staff": "персонал регистрация хостес технический специалист",
    "transport": "трансфер автобус транспорт логистика",
    "accommodation": "проживание гостиница номер",
    "branding": "брендинг баннер навигация оформление площадки",
    "print": "печать полиграфия бейдж буклет",
    "merch": "сувениры мерч подарки",
    "entertainment": "ведущий артист развлекательная программа",
    "security": "охрана безопасность мероприятия",
}

EVENT_TYPES = {
    "конференц": "конференция",
    "форум": "форум",
    "корпоратив": "корпоратив",
    "презентац": "презентация",
    "выстав": "выставка",
    "семинар": "семинар",
    "образоват": "образовательное мероприятие",
    "ужин": "деловой ужин",
}

CITY_ALIASES = {
    "москве": "Москва",
    "москва": "Москва",
    "санкт-петербурге": "Санкт-Петербург",
    "санкт-петербург": "Санкт-Петербург",
    "екатеринбурге": "Екатеринбург",
    "екатеринбург": "Екатеринбург",
    "казани": "Казань",
    "казань": "Казань",
    "сочи": "Сочи",
}


@dataclass
class ServiceNeed:
    status: str = "unknown"
    quantity_basis: str | None = None
    search_queries: list[str] = field(default_factory=list)
    candidate_items: list[dict[str, Any]] = field(default_factory=list)
    selected_item_ids: list[str] = field(default_factory=list)
    budget_lines: list[dict[str, Any]] = field(default_factory=list)
    open_questions: list[str] = field(default_factory=list)

    def to_dict(self) -> dict[str, Any]:
        return {
            "status": self.status,
            "quantity_basis": self.quantity_basis,
            "search_queries": self.search_queries,
            "candidate_items": self.candidate_items,
            "selected_item_ids": self.selected_item_ids,
            "budget_lines": self.budget_lines,
            "open_questions": self.open_questions,
        }


def default_service_needs() -> dict[str, ServiceNeed]:
    return {service_type: ServiceNeed() for service_type in SERVICE_LABELS}


@dataclass
class BriefState:
    stage: str = "intake"
    event_type: str | None = None
    goal: str | None = None
    city: str | None = None
    date: str | None = None
    duration_days: int | None = None
    guests_count: int | None = None
    format: str | None = None
    budget_limit: float | None = None
    budget_tier: str | None = None
    concept: str | None = None
    audience: str | None = None
    vip_or_speakers: str | None = None
    program_notes: str | None = None
    confirmed_requirements: list[str] = field(default_factory=list)
    service_needs: dict[str, ServiceNeed] = field(default_factory=default_service_needs)
    selected_price_items: list[dict[str, Any]] = field(default_factory=list)
    open_questions: list[str] = field(default_factory=list)
    assumptions: list[str] = field(default_factory=list)
    conversation_history: list[dict[str, str]] = field(default_factory=list)

    def to_dict(self) -> dict[str, Any]:
        return {
            "stage": self.stage,
            "event_type": self.event_type,
            "goal": self.goal,
            "city": self.city,
            "date": self.date,
            "duration_days": self.duration_days,
            "guests_count": self.guests_count,
            "format": self.format,
            "budget_limit": self.budget_limit,
            "budget_tier": self.budget_tier,
            "concept": self.concept,
            "audience": self.audience,
            "vip_or_speakers": self.vip_or_speakers,
            "program_notes": self.program_notes,
            "confirmed_requirements": self.confirmed_requirements,
            "service_needs": {
                service_type: need.to_dict()
                for service_type, need in self.service_needs.items()
            },
            "selected_price_items": self.selected_price_items,
            "open_questions": self.open_questions,
            "assumptions": self.assumptions,
            "conversation_turns": sum(
                1 for item in self.conversation_history if item.get("role") == "user"
            ),
        }


class BriefWorkflowState(TypedDict, total=False):
    state: BriefState
    message: str
    searcher: Searcher
    blocking_questions: list[str]
    found_items: list[dict[str, Any]]
    budget: dict[str, Any]
    fallback: str


def _clean(value: Any) -> str:
    return str(value or "").strip()


def _contains_any(text: str, needles: list[str]) -> bool:
    return any(needle in text for needle in needles)


def _extract_city(message: str) -> str | None:
    city_match = re.search(
        r"(?:в городе|город|в)\s+([А-ЯЁA-Z][а-яёa-zA-Z-]+(?:\s*-\s*[А-ЯЁA-Z][а-яёa-zA-Z-]+)?)",
        message,
    )
    if not city_match:
        return None
    raw = city_match.group(1).strip(" .,!?:;")
    normalized = normalize_city(raw)
    return CITY_ALIASES.get(normalized, raw)


def _extract_duration_days(lowered: str) -> int | None:
    match = re.search(r"(\d{1,2})\s*(?:дня|дней|день)", lowered)
    if match:
        return int(match.group(1))
    return None


def _extract_goal(message: str) -> str | None:
    match = re.search(r"(?:цель|задача)\s*[:—-]\s*([^.!?]+)", message, flags=re.IGNORECASE)
    return match.group(1).strip() if match else None


def _extract_concept(message: str) -> str | None:
    match = re.search(r"(?:концепт|концепция)\s*[:—-]\s*([^.!?]+)", message, flags=re.IGNORECASE)
    return match.group(1).strip() if match else None


def update_brief_state(state: BriefState, message: str) -> BriefState:
    lowered = message.lower().replace("ё", "е")

    for needle, value in EVENT_TYPES.items():
        if needle in lowered:
            state.event_type = value
            break

    if any(word in lowered for word in ["офлайн", "очно", "живое"]):
        state.format = "офлайн"
    elif "онлайн" in lowered:
        state.format = "онлайн"
    elif "гибрид" in lowered:
        state.format = "гибрид"

    city = _extract_city(message)
    if city:
        state.city = city

    guests_match = re.search(r"(\d{1,5})\s*(?:человек|участник|гост)", lowered)
    if guests_match:
        state.guests_count = int(guests_match.group(1))

    duration_days = _extract_duration_days(lowered)
    if duration_days:
        state.duration_days = duration_days

    budget_match = re.search(r"(\d+(?:[.,]\d+)?)\s*(?:млн|миллион)", lowered)
    if budget_match:
        state.budget_limit = float(budget_match.group(1).replace(",", ".")) * 1_000_000
    else:
        budget_match = re.search(r"(\d[\d\s]{4,})\s*(?:руб|₽|р)", lowered)
        if budget_match:
            state.budget_limit = float(budget_match.group(1).replace(" ", ""))

    for tier in ["эконом", "стандарт", "премиум"]:
        if tier in lowered:
            state.budget_tier = tier

    goal = _extract_goal(message)
    if goal:
        state.goal = goal
    concept = _extract_concept(message)
    if concept:
        state.concept = concept

    for service_type, keywords in SERVICE_KEYWORDS.items():
        if _contains_any(lowered, keywords):
            need = state.service_needs[service_type]
            need.status = "needed"
            need.quantity_basis = _quantity_basis_for_service(service_type, state)

    state.confirmed_requirements = build_confirmed_requirements(state)
    return state


def _quantity_basis_for_service(service_type: str, state: BriefState) -> str:
    if service_type in {"catering", "merch"}:
        return "по количеству гостей"
    if service_type == "accommodation":
        return "по количеству гостей и ночей"
    if service_type in {"venue", "av_equipment", "staff", "transport", "branding", "print"}:
        return "фиксированная услуга или по дням"
    return "требует уточнения"


def build_confirmed_requirements(state: BriefState) -> list[str]:
    requirements = []
    if state.event_type:
        requirements.append(f"Тип мероприятия: {state.event_type}")
    if state.city:
        requirements.append(f"Город: {state.city}")
    if state.guests_count:
        requirements.append(f"Участников: {state.guests_count}")
    if state.format:
        requirements.append(f"Формат: {state.format}")
    if state.budget_limit:
        requirements.append(f"Бюджетный лимит: {state.budget_limit:,.0f} ₽".replace(",", " "))
    elif state.budget_tier:
        requirements.append(f"Бюджетный уровень: {state.budget_tier}")
    for service_type, need in state.service_needs.items():
        if need.status == "needed":
            requirements.append(f"Нужен блок: {SERVICE_LABELS[service_type]}")
    return requirements


def blocking_questions(state: BriefState) -> list[str]:
    questions = []
    if not state.event_type:
        questions.append("Какой тип мероприятия планируется?")
    if not state.city:
        questions.append("Где и когда пройдет мероприятие: город, дата и длительность?")
    if not state.guests_count:
        questions.append("Сколько участников ожидается?")
    if not state.budget_limit and not state.budget_tier:
        questions.append("Есть ориентир по бюджету: лимит или уровень эконом/стандарт/премиум?")
    if not questions and not needed_service_types(state):
        questions.append(
            "Какие блоки услуг нужны: площадка, питание, оборудование, персонал, транспорт, проживание, брендинг?"
        )
    return questions[:4]


def followup_questions(state: BriefState) -> list[str]:
    questions = []
    if not state.date:
        questions.append("Какая дата и длительность мероприятия?")
    if not state.goal and not state.concept:
        questions.append("Есть ли цель, концепт или ключевая идея мероприятия?")
    return questions[:4]


def needed_service_types(state: BriefState) -> list[str]:
    return [
        service_type
        for service_type, need in state.service_needs.items()
        if need.status == "needed"
    ]


def build_service_query(service_type: str, state: BriefState, message: str) -> str:
    lowered = message.lower().replace("ё", "е")
    query = SERVICE_QUERIES[service_type]
    if service_type == "catering":
        if "кофе" in lowered:
            query = "кофе-брейк питание"
        elif "ужин" in lowered:
            query = "ужин питание банкет"
        elif "обед" in lowered:
            query = "обед питание"
    if service_type == "av_equipment" and "микроф" in lowered:
        query = "радиомикрофон звук оборудование"
    context = " ".join(part for part in [query, state.event_type or "", state.city or ""] if part)
    return context.strip()


def search_catalog_for_services(
    state: BriefState,
    message: str,
    searcher: Searcher,
) -> list[dict[str, Any]]:
    found_items: list[dict[str, Any]] = []
    city_filter = normalize_city(state.city) if state.city else None
    for service_type in needed_service_types(state):
        query = build_service_query(service_type, state, message)
        filters = {"service_type": service_type, "only_active": True}
        if city_filter:
            filters["city"] = city_filter
        items = searcher.search(query, limit=5, filters=filters)
        need = state.service_needs[service_type]
        need.search_queries = [query]
        need.candidate_items = items
        found_items.extend(items)
    return found_items


def _derive_quantity(line: dict[str, Any]) -> tuple[float, str]:
    if line.get("quantity") not in (None, ""):
        return float(line.get("quantity") or 1), _clean(line.get("comment"))

    quantity_kind = line.get("quantity_kind")
    guests_count = float(line.get("guests_count") or 1)
    duration_days = float(line.get("duration_days") or 1)
    comment = _clean(line.get("comment"))

    if quantity_kind == "per_guest":
        return guests_count, comment or "Рассчитано по количеству гостей"
    if quantity_kind == "per_guest_night":
        return guests_count, comment or "Рассчитано по количеству гостей; ночи уточняются отдельно"
    if quantity_kind == "per_day":
        return duration_days, comment or "Рассчитано по длительности мероприятия"
    if quantity_kind == "manual_review":
        return 1.0, comment or "Единица измерения требует ручной проверки"
    return 1.0, comment or "Фиксированная позиция"


def estimate_budget(lines: list[dict[str, Any]]) -> dict[str, Any]:
    total = 0.0
    result_lines = []
    for line in lines:
        unit_price = float(line["unit_price"])
        quantity, comment = _derive_quantity(line)
        multiplier = float(line.get("multiplier", 1) or 1)
        subtotal = unit_price * quantity * multiplier
        total += subtotal
        result_lines.append({**line, "quantity": quantity, "comment": comment, "subtotal": subtotal})
    return {"lines": result_lines, "total": total}


def budget_lines_from_results(results: list[dict[str, Any]], state: BriefState) -> list[dict[str, Any]]:
    lines = []
    used_service_types: set[str] = set()
    selected_ids = {
        str(item_id)
        for need in state.service_needs.values()
        for item_id in need.selected_item_ids
    }
    selected_ids.update(
        str(_payload(item).get("id"))
        for item in state.selected_price_items
        if _payload(item).get("id")
    )
    if not selected_ids:
        return lines

    for result in results:
        payload = result.get("payload", result)
        item_id = str(payload.get("id", result.get("id")) or "")
        if item_id not in selected_ids:
            continue
        service_type = payload.get("service_type")
        if service_type in used_service_types:
            continue
        used_service_types.add(service_type)
        lines.append(
            {
                "item_id": payload.get("id", result.get("id")),
                "name": payload.get("name", result.get("name")),
                "unit": payload.get("unit", result.get("unit")),
                "unit_price": payload.get("unit_price", result.get("unit_price", 0)),
                "quantity_kind": payload.get("quantity_kind", "manual_review"),
                "guests_count": state.guests_count or 1,
                "duration_days": state.duration_days or 1,
                "supplier": payload.get("supplier", result.get("supplier")),
                "service_type": service_type,
            }
        )
    return lines


def _format_money(value: Any) -> str:
    try:
        amount = float(value)
    except (TypeError, ValueError):
        return "цена не указана"
    if amount.is_integer():
        return f"{int(amount):,}".replace(",", " ") + " ₽"
    return f"{amount:,.2f}".replace(",", " ").replace(".", ",") + " ₽"


def _payload(item: dict[str, Any]) -> dict[str, Any]:
    payload = item.get("payload")
    return payload if isinstance(payload, dict) else item


def _candidate_service_type(item: dict[str, Any]) -> str | None:
    payload = _payload(item)
    return payload.get("service_type")


def _render_candidate_shortlist(found_items: list[dict[str, Any]]) -> list[str]:
    lines = ["\nКороткий список подрядчиков:"]
    lines.append("Это кандидаты для выбора менеджером, не финальный состав подрядчиков.")

    for service_type in SERVICE_LABELS:
        service_items = [
            item for item in found_items if _candidate_service_type(item) == service_type
        ]
        if not service_items:
            continue

        label = SERVICE_LABELS[service_type]
        lines.append(f"\n{label}:")
        suppliers: dict[str, list[dict[str, Any]]] = {}
        for item in service_items:
            payload = _payload(item)
            supplier = payload.get("supplier") or "поставщик не указан"
            suppliers.setdefault(supplier, []).append(payload)

        for supplier, items in suppliers.items():
            lines.append(f"- {supplier}")
            for payload in items:
                lines.append(
                    f"  - ID {payload.get('id')}: {payload.get('name')} — "
                    f"{_format_money(payload.get('unit_price'))} / {payload.get('unit') or 'ед.'}"
                )

    unknown_items = [
        item for item in found_items if _candidate_service_type(item) not in SERVICE_LABELS
    ]
    if unknown_items:
        lines.append("\nБез категории услуги:")
        for item in unknown_items:
            payload = _payload(item)
            lines.append(
                f"- {payload.get('supplier') or 'поставщик не указан'}: "
                f"ID {payload.get('id')}: {payload.get('name')} — "
                f"{_format_money(payload.get('unit_price'))} / {payload.get('unit') or 'ед.'}"
            )

    return lines


def default_answer(state: BriefState, found_items: list[dict[str, Any]], budget: dict[str, Any]) -> str:
    if state.open_questions and not found_items:
        return "Нужны уточнения, чтобы собрать бриф:\n" + "\n".join(
            f"- {question}" for question in state.open_questions
        )

    parts = ["Черновик брифа мероприятия"]
    if state.confirmed_requirements:
        parts.append("\nПодтвержденные вводные:")
        parts.extend(f"- {item}" for item in state.confirmed_requirements)

    if found_items:
        parts.extend(_render_candidate_shortlist(found_items))
    else:
        parts.append("\nВ каталоге нет подходящих строк по текущим вводным и фильтрам.")

    if budget["lines"]:
        parts.append(f"\nОриентировочная смета по выбранным позициям: {_format_money(budget['total'])}")
        parts.append("Это расчетный ориентир; финальный состав подрядчиков выбирает менеджер.")
        for line in budget["lines"]:
            parts.append(
                f"- {line['name']}: {_format_money(line['unit_price'])} × "
                f"{line['quantity']:g} = {_format_money(line['subtotal'])}"
            )

    questions = state.open_questions or followup_questions(state)
    if questions:
        parts.append("\nОткрытые вопросы:")
        parts.extend(f"- {question}" for question in questions)
    return "\n".join(parts)


def format_conversation_history(history: list[dict[str, str]]) -> str:
    if not history:
        return "История диалога пока пустая."

    lines = []
    for item in history:
        role = "Пользователь" if item.get("role") == "user" else "ARGUS"
        content = item.get("content", "").strip()
        if content:
            lines.append(f"{role}: {content}")
    return "\n".join(lines) if lines else "История диалога пока пустая."


def _run_workflow(state: BriefState, message: str, searcher: Searcher) -> dict[str, Any]:
    def fact_extraction(workflow: BriefWorkflowState) -> BriefWorkflowState:
        update_brief_state(workflow["state"], workflow["message"])
        return {"state": workflow["state"]}

    def missing_info_check(workflow: BriefWorkflowState) -> BriefWorkflowState:
        questions = blocking_questions(workflow["state"])
        workflow["state"].open_questions = questions
        workflow["state"].stage = "intake" if questions else "service_planning"
        return {"state": workflow["state"], "blocking_questions": questions}

    def service_planning(workflow: BriefWorkflowState) -> BriefWorkflowState:
        if workflow.get("blocking_questions"):
            return {"found_items": []}
        workflow["state"].stage = "catalog_search"
        return {"state": workflow["state"]}

    def catalog_search(workflow: BriefWorkflowState) -> BriefWorkflowState:
        if workflow.get("blocking_questions"):
            return {"found_items": []}
        found_items = search_catalog_for_services(
            workflow["state"],
            workflow["message"],
            workflow["searcher"],
        )
        return {"found_items": found_items}

    def budget_estimation(workflow: BriefWorkflowState) -> BriefWorkflowState:
        budget_lines = budget_lines_from_results(workflow.get("found_items", []), workflow["state"])
        budget = estimate_budget(budget_lines)
        return {"state": workflow["state"], "budget": budget}

    def response_generation(workflow: BriefWorkflowState) -> BriefWorkflowState:
        if not workflow.get("blocking_questions") and workflow.get("found_items"):
            workflow["state"].stage = "shortlist_brief"
            workflow["state"].open_questions = followup_questions(workflow["state"])
        fallback = default_answer(
            workflow["state"],
            workflow.get("found_items", []),
            workflow.get("budget", {"lines": [], "total": 0}),
        )
        return {"state": workflow["state"], "fallback": fallback}

    initial: BriefWorkflowState = {"state": state, "message": message, "searcher": searcher}
    if StateGraph is None:
        workflow = {**initial, **fact_extraction(initial)}
        workflow = {**workflow, **missing_info_check(workflow)}
        workflow = {**workflow, **service_planning(workflow)}
        workflow = {**workflow, **catalog_search(workflow)}
        workflow = {**workflow, **budget_estimation(workflow)}
        workflow = {**workflow, **response_generation(workflow)}
        return dict(workflow)

    graph = StateGraph(BriefWorkflowState)
    graph.add_node("fact_extraction", fact_extraction)
    graph.add_node("missing_info_check", missing_info_check)
    graph.add_node("service_planning", service_planning)
    graph.add_node("catalog_search", catalog_search)
    graph.add_node("budget_estimation", budget_estimation)
    graph.add_node("response_generation", response_generation)
    graph.set_entry_point("fact_extraction")
    graph.add_edge("fact_extraction", "missing_info_check")
    graph.add_edge("missing_info_check", "service_planning")
    graph.add_edge("service_planning", "catalog_search")
    graph.add_edge("catalog_search", "budget_estimation")
    graph.add_edge("budget_estimation", "response_generation")
    graph.add_edge("response_generation", END)
    return dict(graph.compile().invoke(initial))


def run_brief_turn(
    state: BriefState,
    message: str,
    searcher: Searcher,
    chat_client: ChatClient | None = None,
) -> dict[str, Any]:
    prior_history = list(state.conversation_history)
    workflow = _run_workflow(state, message, searcher)
    found_items = workflow.get("found_items", [])
    budget = workflow.get("budget", {"lines": [], "total": 0})
    fallback = workflow.get("fallback") or default_answer(state, found_items, budget)

    answer = fallback
    if chat_client:
        history_text = format_conversation_history(prior_history)
        prompt = (
            "Сформулируй короткий ответ менеджеру на русском как продолжение текущего диалога. "
            "Не меняй факты, не добавляй цены и не повторяй уже заданные вопросы.\n\n"
            "ui_mode=brief_workspace\n"
            f"История текущего диалога:\n{history_text}\n\n"
            f"Текущий запрос пользователя:\n{message}\n\n"
            f"brief={state.to_dict()}\n"
            f"found_items={found_items[:9]}\n"
            "item_details=[]\n"
            "verification_results=[]\n"
            f"budget={budget}\n\n"
            f"Черновик ответа:\n{fallback}"
        )
        try:
            answer = chat_client.complete(COMPOSER_SYSTEM_PROMPT, prompt)
        except Exception:
            answer = fallback

    state.conversation_history.append({"role": "user", "content": message})
    state.conversation_history.append({"role": "assistant", "content": answer})

    return {
        "message": answer,
        "brief_state": state.to_dict(),
        "found_items": found_items[:10],
        "budget": budget,
    }
