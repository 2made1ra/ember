from __future__ import annotations

from typing import Any

from qdrant_client import QdrantClient
from qdrant_client.http import models

from .catalog import CatalogItem
from .config import Settings
from .errors import DependencyUnavailableError


class QdrantPriceStore:
    def __init__(self, settings: Settings):
        self.settings = settings
        self.client = QdrantClient(
            url=settings.qdrant_url,
            api_key=settings.qdrant_api_key,
            timeout=120,
            check_compatibility=False,
        )
        self.collection = settings.qdrant_collection

    def recreate_collection(self, vector_size: int) -> None:
        try:
            self.client.recreate_collection(
                collection_name=self.collection,
                vectors_config=models.VectorParams(
                    size=vector_size,
                    distance=models.Distance.COSINE,
                ),
            )
        except Exception as exc:
            raise DependencyUnavailableError(
                "Qdrant недоступен: не удалось пересоздать коллекцию "
                f"`{self.collection}` на {self.settings.qdrant_url}. "
                "Запустите `make qdrant` или `docker compose up -d qdrant`."
            ) from exc

    def upsert_items(self, items: list[CatalogItem], vectors: list[list[float]]) -> None:
        points = [
            models.PointStruct(
                id=index + 1,
                vector=vector,
                payload=item.payload,
            )
            for index, (item, vector) in enumerate(zip(items, vectors, strict=True))
        ]
        try:
            self.client.upsert(collection_name=self.collection, points=points)
        except Exception as exc:
            raise DependencyUnavailableError(
                "Qdrant недоступен: не удалось загрузить точки в коллекцию "
                f"`{self.collection}` на {self.settings.qdrant_url}."
            ) from exc

    def _build_filter(self, filters: dict[str, Any] | None) -> models.Filter | None:
        if not filters:
            return None

        conditions = []
        if filters.get("service_type"):
            conditions.append(
                models.FieldCondition(
                    key="service_type",
                    match=models.MatchValue(value=filters["service_type"]),
                )
            )
        if filters.get("city"):
            conditions.append(
                models.FieldCondition(
                    key="city_normalized",
                    match=models.MatchValue(value=filters["city"]),
                )
            )
        if filters.get("only_active"):
            conditions.append(
                models.FieldCondition(
                    key="supplier_status_normalized",
                    match=models.MatchValue(value="активен"),
                )
            )
        if not conditions:
            return None
        return models.Filter(must=conditions)

    def search(
        self,
        query_vector: list[float],
        limit: int = 10,
        filters: dict[str, Any] | None = None,
    ) -> list[dict[str, Any]]:
        try:
            query_filter = self._build_filter(filters)
            query_kwargs: dict[str, Any] = {
                "collection_name": self.collection,
                "query": query_vector,
                "limit": limit,
                "with_payload": True,
            }
            if query_filter is not None:
                query_kwargs["query_filter"] = query_filter
            response = self.client.query_points(
                **query_kwargs,
            )
        except Exception as exc:
            raise DependencyUnavailableError(
                "Qdrant недоступен: не удалось выполнить поиск в коллекции "
                f"`{self.collection}` на {self.settings.qdrant_url}."
            ) from exc
        return [
            {
                "score": float(result.score),
                "payload": result.payload or {},
            }
            for result in response.points
        ]
