from __future__ import annotations

import threading
from dataclasses import dataclass, field
from typing import Any

from .brief import BriefState


@dataclass
class CatalogStatus:
    ready: bool = False
    stage: str = "idle"
    message: str = "Каталог не загружен"
    row_count: int = 0
    embedded_count: int = 0
    vector_size: int | None = None
    error: str | None = None

    def to_dict(self) -> dict[str, Any]:
        return {
            "ready": self.ready,
            "stage": self.stage,
            "message": self.message,
            "row_count": self.row_count,
            "embedded_count": self.embedded_count,
            "vector_size": self.vector_size,
            "error": self.error,
        }


@dataclass
class AppState:
    catalog: CatalogStatus = field(default_factory=CatalogStatus)
    brief: BriefState = field(default_factory=BriefState)


STATE = AppState()
LOCK = threading.RLock()


def reset_app_state() -> None:
    with LOCK:
        STATE.catalog = CatalogStatus()
        STATE.brief = BriefState()


def set_catalog_status(**kwargs: Any) -> CatalogStatus:
    with LOCK:
        for key, value in kwargs.items():
            setattr(STATE.catalog, key, value)
        return STATE.catalog


def get_catalog_status() -> CatalogStatus:
    with LOCK:
        return STATE.catalog


def reset_brief_state() -> BriefState:
    with LOCK:
        STATE.brief = BriefState()
        return STATE.brief


def get_brief_state() -> BriefState:
    with LOCK:
        return STATE.brief
