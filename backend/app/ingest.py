from __future__ import annotations

from .catalog import CatalogValidationError, parse_catalog_csv
from .config import Settings
from .errors import DependencyUnavailableError
from .state import reset_brief_state, set_catalog_status
from .vector_store import QdrantPriceStore


def ingest_catalog(content: bytes, settings: Settings) -> None:
    try:
        set_catalog_status(
            ready=False,
            stage="parsing",
            message="Читаю CSV и проверяю колонки",
            row_count=0,
            embedded_count=0,
            vector_size=None,
            error=None,
        )
        items = parse_catalog_csv(content)
        vectors = [item.vector for item in items]
        if not vectors or not vectors[0]:
            raise CatalogValidationError("catalog contains empty embeddings")

        set_catalog_status(
            stage="embedding",
            message="Читаю готовые embeddings из CSV",
            row_count=len(items),
            embedded_count=len(vectors),
        )

        vector_size = len(vectors[0])
        set_catalog_status(
            stage="qdrant",
            message="Пересоздаю коллекцию Qdrant",
            vector_size=vector_size,
        )

        store = QdrantPriceStore(settings)
        store.recreate_collection(vector_size)
        set_catalog_status(stage="uploading", message="Загружаю позиции в Qdrant")
        store.upsert_items(items, vectors)

        reset_brief_state()
        set_catalog_status(
            ready=True,
            stage="ready",
            message="Каталог готов",
            row_count=len(items),
            embedded_count=len(vectors),
            vector_size=vector_size,
            error=None,
        )
    except DependencyUnavailableError as exc:
        set_catalog_status(
            ready=False,
            stage="error",
            message="Ошибка загрузки каталога",
            error=str(exc),
        )
    except Exception as exc:
        set_catalog_status(
            ready=False,
            stage="error",
            message="Ошибка загрузки каталога",
            error=str(exc),
        )
