import unittest
from unittest.mock import Mock, patch

import httpx
from fastapi.testclient import TestClient

from app.auth import require_user
from app.errors import DependencyUnavailableError
from app.main import app
from app.state import reset_app_state, set_catalog_status


class ApiTests(unittest.TestCase):
    def setUp(self):
        reset_app_state()
        app.dependency_overrides[require_user] = lambda: {
            "id": "user-1",
            "email": "demo@example.com",
            "app_metadata": {"role": "admin"},
        }
        self.client = TestClient(app)

    def tearDown(self):
        app.dependency_overrides.clear()

    def test_health_remains_public_without_auth(self):
        app.dependency_overrides.clear()

        response = self.client.get("/api/health")

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json(), {"status": "ok"})

    def test_catalog_status_requires_auth_token(self):
        app.dependency_overrides.clear()

        response = self.client.get("/api/catalog/status")

        self.assertEqual(response.status_code, 401)
        self.assertIn("authorization", response.json()["detail"].lower())

    def test_catalog_suppliers_requires_auth_token(self):
        app.dependency_overrides.clear()

        response = self.client.get("/api/catalog/suppliers")

        self.assertEqual(response.status_code, 401)
        self.assertIn("authorization", response.json()["detail"].lower())

    def test_catalog_status_accepts_local_bearer_token(self):
        app.dependency_overrides.clear()

        store = Mock()
        store.get_user_for_token.return_value = {
            "id": "user-1",
            "email": "demo@example.com",
            "app_metadata": {"role": "user"},
        }

        with patch("app.auth.get_auth_store", return_value=store):
            response = self.client.get(
                "/api/catalog/status",
                headers={"Authorization": "Bearer valid-token"},
            )

        self.assertEqual(response.status_code, 200)
        store.get_user_for_token.assert_called_once_with("valid-token")

    def test_catalog_status_rejects_invalid_local_token(self):
        app.dependency_overrides.clear()
        store = Mock()
        store.get_user_for_token.return_value = None

        with patch("app.auth.get_auth_store", return_value=store):
            result = self.client.get(
                "/api/catalog/status",
                headers={"Authorization": "Bearer invalid-token"},
            )

        self.assertEqual(result.status_code, 401)
        self.assertIn("invalid", result.json()["detail"].lower())

    def test_auth_signup_returns_bearer_session(self):
        app.dependency_overrides.clear()
        store = Mock()
        store.create_user.return_value = {
            "id": "user-1",
            "email": "demo@example.com",
            "app_metadata": {"role": "user"},
        }
        store.create_session.return_value = {
            "access_token": "local-token",
            "token_type": "bearer",
            "expires_in": 3600,
            "user": store.create_user.return_value,
        }

        with patch("app.main.get_auth_store", return_value=store):
            response = self.client.post(
                "/api/auth/signup",
                json={"email": "demo@example.com", "password": "developer-password"},
            )

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json()["access_token"], "local-token")
        self.assertEqual(response.json()["user"]["email"], "demo@example.com")
        store.create_user.assert_called_once_with("demo@example.com", "developer-password", role="user")
        store.create_session.assert_called_once_with(store.create_user.return_value)

    def test_auth_signin_rejects_bad_credentials(self):
        app.dependency_overrides.clear()
        store = Mock()
        store.authenticate.return_value = None

        with patch("app.main.get_auth_store", return_value=store):
            response = self.client.post(
                "/api/auth/signin",
                json={"email": "demo@example.com", "password": "wrong-password"},
            )

        self.assertEqual(response.status_code, 401)
        self.assertIn("invalid", response.json()["detail"].lower())

    def test_auth_session_returns_current_user(self):
        app.dependency_overrides.clear()
        store = Mock()
        store.get_user_for_token.return_value = {
            "id": "user-1",
            "email": "demo@example.com",
            "app_metadata": {"role": "user"},
        }

        with patch("app.auth.get_auth_store", return_value=store):
            response = self.client.get(
                "/api/auth/session",
                headers={"Authorization": "Bearer local-token"},
            )

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json()["user"]["email"], "demo@example.com")

    def test_auth_logout_revokes_current_token(self):
        app.dependency_overrides.clear()
        store = Mock()
        store.get_user_for_token.return_value = {
            "id": "user-1",
            "email": "demo@example.com",
            "app_metadata": {"role": "user"},
        }

        with patch("app.auth.get_auth_store", return_value=store), patch(
            "app.main.get_auth_store",
            return_value=store,
        ):
            response = self.client.post(
                "/api/auth/logout",
                headers={"Authorization": "Bearer local-token"},
            )

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json(), {"status": "ok"})
        store.revoke_token.assert_called_once_with("local-token")

    def test_catalog_status_starts_without_loaded_catalog(self):
        response = self.client.get("/api/catalog/status")

        self.assertEqual(response.status_code, 200)
        body = response.json()
        self.assertFalse(body["ready"])
        self.assertEqual(body["stage"], "idle")
        self.assertEqual(body["row_count"], 0)

    def test_chat_requires_loaded_catalog(self):
        response = self.client.post(
            "/api/chat",
            json={"message": "Нужен бриф на конференцию", "mode": "brief"},
        )

        self.assertEqual(response.status_code, 409)
        self.assertIn("catalog", response.json()["detail"].lower())

    def test_search_requires_loaded_catalog(self):
        response = self.client.post(
            "/api/search",
            json={"query": "ужин на 30 человек"},
        )

        self.assertEqual(response.status_code, 409)
        self.assertIn("catalog", response.json()["detail"].lower())

    def test_catalog_suppliers_requires_loaded_catalog(self):
        response = self.client.get("/api/catalog/suppliers")

        self.assertEqual(response.status_code, 409)
        self.assertIn("catalog", response.json()["detail"].lower())

    def test_catalog_supplier_detail_requires_loaded_catalog(self):
        response = self.client.get("/api/catalog/suppliers/7704856280")

        self.assertEqual(response.status_code, 409)
        self.assertIn("catalog", response.json()["detail"].lower())

    def test_catalog_suppliers_returns_grouped_store_rows(self):
        store = Mock()
        store.list_suppliers.return_value = [
            {
                "id": "7704856280",
                "name": "ООО Питание",
                "inn": "7704856280",
                "city": "Москва",
                "status": "Активен",
                "item_count": 2,
                "service_types": ["catering"],
                "min_price": 450.0,
            }
        ]
        set_catalog_status(ready=True, stage="ready", row_count=1565)

        with patch("app.main.PostgresCatalogStore", return_value=store):
            response = self.client.get("/api/catalog/suppliers?limit=20&query=пит")

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json()["suppliers"][0]["id"], "7704856280")
        store.list_suppliers.assert_called_once_with(limit=20, query="пит")

    def test_catalog_supplier_detail_returns_items(self):
        store = Mock()
        store.get_supplier.return_value = {
            "id": "7704856280",
            "name": "ООО Питание",
            "inn": "7704856280",
            "city": "Москва",
            "phone": "+7",
            "email": "sales@example.test",
            "status": "Активен",
            "items": [
                {
                    "id": "item-1",
                    "name": "Кофе-брейк",
                    "category": "Питание",
                    "unit": "чел",
                    "unit_price": 450.0,
                    "service_type": "catering",
                }
            ],
        }
        set_catalog_status(ready=True, stage="ready", row_count=1565)

        with patch("app.main.PostgresCatalogStore", return_value=store):
            response = self.client.get("/api/catalog/suppliers/7704856280")

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json()["supplier"]["items"][0]["id"], "item-1")
        store.get_supplier.assert_called_once_with("7704856280")

    def test_catalog_supplier_detail_accepts_url_safe_fallback_supplier_id(self):
        store = Mock()
        store.get_supplier.return_value = {
            "id": "ооо-ромашка-север",
            "name": "ООО Ромашка / Север",
            "inn": None,
            "city": "Москва",
            "phone": None,
            "email": None,
            "status": "Активен",
            "items": [],
        }
        set_catalog_status(ready=True, stage="ready", row_count=1565)

        with patch("app.main.PostgresCatalogStore", return_value=store):
            response = self.client.get("/api/catalog/suppliers/ооо-ромашка-север")

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json()["supplier"]["name"], "ООО Ромашка / Север")
        store.get_supplier.assert_called_once_with("ооо-ромашка-север")

    def test_catalog_supplier_detail_returns_404_for_unknown_supplier(self):
        store = Mock()
        store.get_supplier.return_value = None
        set_catalog_status(ready=True, stage="ready", row_count=1565)

        with patch("app.main.PostgresCatalogStore", return_value=store):
            response = self.client.get("/api/catalog/suppliers/missing")

        self.assertEqual(response.status_code, 404)

    def test_search_returns_semantic_results(self):
        class FakeSearcher:
            last_limit = None

            def __init__(self, settings):
                pass

            def search(self, query, limit=8):
                FakeSearcher.last_limit = limit
                return [
                    {
                        "score": 0.88,
                        "payload": {
                            "id": "77",
                            "name": "Организация ужина",
                            "unit": "чел",
                            "unit_price": 1200,
                            "supplier": "Тестовый поставщик",
                        },
                    }
                ][:limit]

        set_catalog_status(ready=True, stage="ready", row_count=1565)

        with patch("app.main.PriceSearcher", FakeSearcher):
            response = self.client.post(
                "/api/search",
                json={"query": "ужин на 30 человек", "limit": 5},
            )

        self.assertEqual(response.status_code, 200)
        body = response.json()
        self.assertEqual(body["query"], "ужин на 30 человек")
        self.assertEqual(body["items"][0]["payload"]["id"], "77")
        self.assertTrue(body["message"].startswith("1. "))
        self.assertIn("Организация ужина", body["message"])
        self.assertIn("1 200 ₽ за чел", body["message"])
        self.assertIn("Тестовый поставщик", body["message"])
        self.assertNotIn("score", body["message"].lower())
        self.assertNotIn("0.88", body["message"])
        self.assertEqual(FakeSearcher.last_limit, 5)

    def test_search_defaults_to_top_3(self):
        class FakeSearcher:
            last_limit = None

            def __init__(self, settings):
                pass

            def search(self, query, limit=8):
                FakeSearcher.last_limit = limit
                return []

        set_catalog_status(ready=True, stage="ready", row_count=1565)

        with patch("app.main.PriceSearcher", FakeSearcher):
            response = self.client.post(
                "/api/search",
                json={"query": "кофе брейк"},
            )

        self.assertEqual(response.status_code, 200)
        self.assertEqual(FakeSearcher.last_limit, 3)

    def test_chat_returns_json_when_dependency_is_unavailable(self):
        class FailingSearcher:
            def __init__(self, settings):
                pass

            def search(self, query, limit=8, filters=None):
                raise DependencyUnavailableError("PostgreSQL недоступен")

        set_catalog_status(ready=True, stage="ready")
        client = TestClient(app, raise_server_exceptions=False)

        with patch("app.main.PriceSearcher", FailingSearcher):
            response = client.post(
                "/api/chat",
                json={
                    "message": (
                        "Нужна офлайн конференция в Москве на 30 человек, "
                        "нужен ужин, бюджет стандарт"
                    ),
                    "mode": "brief",
                },
            )

        self.assertEqual(response.status_code, 503)
        self.assertEqual(response.json()["detail"], "PostgreSQL недоступен")

    def test_chat_endpoint_routes_search_requests_on_backend(self):
        class FakeSearcher:
            calls = []

            def __init__(self, settings):
                pass

            def search(self, query, limit=8, filters=None):
                FakeSearcher.calls.append({"query": query, "limit": limit, "filters": filters})
                return [
                    {
                        "score": 0.88,
                        "payload": {
                            "id": "664",
                            "name": "Радиомикрофон",
                            "unit": "шт",
                            "unit_price": 1230,
                            "supplier": "Премьер-Шоу",
                            "supplier_city": "Екатеринбург",
                        },
                    }
                ]

        class FakeChatClient:
            calls = []

            def __init__(self, settings):
                pass

            def complete(self, system, user):
                FakeChatClient.calls.append({"system": system, "user": user})
                if "ARGUS Router" in system:
                    return """
                    {
                      "interface_mode": "chat_search",
                      "intent": "supplier_search",
                      "workflow_stage": "searching",
                      "confidence": 0.95,
                      "reason_codes": ["catalog_search"],
                      "brief_update": {},
                      "search_requests": [
                        {
                          "query": "радиомикрофон",
                          "service_category": "звук",
                          "filters": {
                            "supplier_city_normalized": "екатеринбург",
                            "category": null,
                            "supplier_status_normalized": null,
                            "has_vat": null,
                            "vat_mode": null,
                            "unit_price_min": null,
                            "unit_price_max": null
                          },
                          "priority": 1,
                          "limit": 8
                        }
                      ],
                      "tool_intents": ["search_items"],
                      "missing_fields": [],
                      "clarification_questions": []
                    }
                    """
                return "Нашел варианты в каталоге. Это предварительные кандидаты."

        set_catalog_status(ready=True, stage="ready", row_count=1565)

        with patch("app.main.PriceSearcher", FakeSearcher), patch("app.main.LMStudioClient", FakeChatClient):
            response = self.client.post(
                "/api/chat",
                json={"message": "Найди радиомикрофоны в Екатеринбурге", "mode": "brief"},
            )

        self.assertEqual(response.status_code, 200)
        self.assertEqual(FakeSearcher.calls[0]["query"], "радиомикрофон")
        self.assertEqual(
            FakeSearcher.calls[0]["filters"],
            {"city": "екатеринбург"},
        )
        self.assertEqual(response.json()["route"]["interface_mode"], "chat_search")
        self.assertEqual(response.json()["items"][0]["payload"]["id"], "664")
        self.assertIn("предварительные кандидаты", response.json()["message"])

    def test_chat_endpoint_selects_previous_ad_hoc_search_result_by_id(self):
        class FakeSearcher:
            calls = []

            def __init__(self, settings):
                pass

            def search(self, query, limit=8, filters=None):
                FakeSearcher.calls.append({"query": query, "limit": limit, "filters": filters})
                return [
                    {
                        "score": 0.88,
                        "payload": {
                            "id": "664",
                            "name": "Радиомикрофон",
                            "unit": "шт",
                            "unit_price": 1230,
                            "supplier": "Премьер-Шоу",
                            "supplier_city": "Екатеринбург",
                            "quantity_kind": "fixed",
                        },
                    }
                ]

        class FakeChatClient:
            def __init__(self, settings):
                pass

            def complete(self, system, user):
                if "ARGUS Router" not in system:
                    return "Ответ ассистента"
                if "Выбери ID 664" in user:
                    return """
                    {
                      "interface_mode": "brief_workspace",
                      "intent": "selection",
                      "workflow_stage": "search_results_shown",
                      "confidence": 0.95,
                      "reason_codes": ["explicit_selection"],
                      "brief_update": {},
                      "search_requests": [],
                      "tool_intents": ["select_item"],
                      "missing_fields": [],
                      "clarification_questions": []
                    }
                    """
                return """
                {
                  "interface_mode": "chat_search",
                  "intent": "supplier_search",
                  "workflow_stage": "searching",
                  "confidence": 0.95,
                  "reason_codes": ["catalog_search"],
                  "brief_update": {},
                  "search_requests": [
                    {
                      "query": "радиомикрофон",
                      "service_category": "звук",
                      "filters": {
                        "supplier_city_normalized": null,
                        "category": null,
                        "supplier_status_normalized": null,
                        "has_vat": null,
                        "vat_mode": null,
                        "unit_price_min": null,
                        "unit_price_max": null
                      },
                      "priority": 1,
                      "limit": 8
                    }
                  ],
                  "tool_intents": ["search_items"],
                  "missing_fields": [],
                  "clarification_questions": []
                }
                """

        set_catalog_status(ready=True, stage="ready", row_count=1565)

        with patch("app.main.PriceSearcher", FakeSearcher), patch("app.main.LMStudioClient", FakeChatClient):
            search_response = self.client.post(
                "/api/chat",
                json={"message": "Найди радиомикрофоны", "mode": "brief"},
            )
            selection_response = self.client.post(
                "/api/chat",
                json={"message": "Выбери ID 664", "mode": "brief"},
            )

        self.assertEqual(search_response.status_code, 200)
        self.assertEqual(search_response.json()["items"][0]["payload"]["id"], "664")
        self.assertEqual(selection_response.status_code, 200)
        selected_price_item_ids = [
            item["payload"]["id"]
            for item in selection_response.json()["brief_state"]["selected_price_items"]
        ]
        self.assertEqual(
            selected_price_item_ids,
            ["664"],
        )
        self.assertEqual(
            [line["item_id"] for line in selection_response.json()["budget"]["lines"]],
            ["664"],
        )
        self.assertEqual(selection_response.json()["budget"]["total"], 1230.0)
        self.assertIn("ID 664", selection_response.json()["message"])

    def test_brief_chat_keeps_dialog_context_between_turns(self):
        class FakeSearcher:
            def __init__(self, settings):
                pass

            def search(self, query, limit=8):
                return []

        class FakeChatClient:
            prompts = []

            def __init__(self, settings):
                pass

            def complete(self, system, user):
                FakeChatClient.prompts.append(user)
                return f"Ответ {len(FakeChatClient.prompts)}"

        set_catalog_status(ready=True, stage="ready", row_count=1565)

        with patch("app.main.PriceSearcher", FakeSearcher), patch("app.main.LMStudioClient", FakeChatClient):
            first = self.client.post(
                "/api/chat",
                json={"message": "Нужен офлайн корпоратив в Москве на 30 человек", "mode": "brief"},
            )
            second = self.client.post(
                "/api/chat",
                json={"message": "Нужен ужин и регистрация гостей", "mode": "brief"},
            )

        self.assertEqual(first.status_code, 200)
        self.assertEqual(second.status_code, 200)
        self.assertIn("Нужен офлайн корпоратив в Москве на 30 человек", FakeChatClient.prompts[1])
        self.assertIn("Ответ 1", FakeChatClient.prompts[1])
        self.assertEqual(second.json()["brief_state"]["conversation_turns"], 2)

    def test_chat_reset_clears_brief_context(self):
        class FakeSearcher:
            def __init__(self, settings):
                pass

            def search(self, query, limit=8):
                return []

        class FakeChatClient:
            prompts = []

            def __init__(self, settings):
                pass

            def complete(self, system, user):
                FakeChatClient.prompts.append(user)
                return "Ответ"

        set_catalog_status(ready=True, stage="ready", row_count=1565)

        with patch("app.main.PriceSearcher", FakeSearcher), patch("app.main.LMStudioClient", FakeChatClient):
            self.client.post(
                "/api/chat",
                json={"message": "Нужен офлайн корпоратив в Москве на 30 человек", "mode": "brief"},
            )
            reset = self.client.post("/api/chat/reset")
            response = self.client.post(
                "/api/chat",
                json={"message": "Теперь нужен форум в Казани", "mode": "brief"},
            )

        self.assertEqual(reset.status_code, 200)
        self.assertEqual(reset.json()["conversation_turns"], 0)
        self.assertEqual(response.status_code, 200)
        self.assertNotIn("Нужен офлайн корпоратив в Москве", FakeChatClient.prompts[-1])


if __name__ == "__main__":
    unittest.main()
