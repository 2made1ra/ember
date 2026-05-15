import os
import unittest
from unittest.mock import patch

from app.config import Settings


class ConfigTests(unittest.TestCase):
    def test_settings_reads_lm_studio_base_url_when_instance_is_created(self):
        with patch.dict(os.environ, {"LM_STUDIO_BASE_URL": "http://192.168.1.44:1234/v1"}):
            settings = Settings()

        self.assertEqual(settings.lm_studio_base_url, "http://192.168.1.44:1234/v1")

    def test_settings_uses_api_key_embedding_endpoint_when_api_key_is_present(self):
        with patch.dict(os.environ, {"API_KEY": "secret"}, clear=True):
            settings = Settings()

        self.assertEqual(settings.embedding_api_key, "secret")
        self.assertEqual(settings.embedding_base_url, "https://api.vsellm.ru/v1")
        self.assertEqual(settings.embedding_model, "openai/text-embedding-3-small")

    def test_settings_uses_api_key_chat_endpoint_when_api_key_is_present(self):
        with patch.dict(os.environ, {"API_KEY": "secret"}, clear=True):
            settings = Settings()

        self.assertEqual(settings.chat_api_key, "secret")
        self.assertEqual(settings.chat_base_url, "https://api.vsellm.ru/v1")
        self.assertEqual(settings.chat_model, "openai/gpt-oss-120b")

    def test_settings_allows_chat_endpoint_override(self):
        with patch.dict(
            os.environ,
            {
                "API_KEY": "shared-secret",
                "CHAT_API_KEY": "chat-secret",
                "CHAT_BASE_URL": "https://example.test/v1",
                "CHAT_MODEL": "custom-chat-model",
            },
            clear=True,
        ):
            settings = Settings()

        self.assertEqual(settings.chat_api_key, "chat-secret")
        self.assertEqual(settings.chat_base_url, "https://example.test/v1")
        self.assertEqual(settings.chat_model, "custom-chat-model")

    def test_settings_reads_postgres_auth_configuration(self):
        with patch.dict(
            os.environ,
            {
                "DATABASE_URL": "postgresql://argus:argus@localhost:5432/argus",
                "AUTH_SESSION_TTL_SECONDS": "7200",
                "DEV_ADMIN_EMAIL": "developer@example.com",
                "DEV_ADMIN_PASSWORD": "developer-password",
            },
            clear=True,
        ):
            settings = Settings()

        self.assertEqual(settings.database_url, "postgresql://argus:argus@localhost:5432/argus")
        self.assertEqual(settings.auth_session_ttl_seconds, 7200)
        self.assertEqual(settings.dev_admin_email, "developer@example.com")
        self.assertEqual(settings.dev_admin_password, "developer-password")
        self.assertEqual(settings.dev_admin_role, "admin")


if __name__ == "__main__":
    unittest.main()
