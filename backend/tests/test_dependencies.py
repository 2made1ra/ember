import unittest
from unittest.mock import Mock, patch

import httpx

from app.config import Settings
from app.errors import DependencyUnavailableError
from app.lm_studio import LMStudioClient


class DependencyErrorTests(unittest.TestCase):
    def test_lm_studio_embedding_connection_refused_is_actionable(self):
        settings = Settings(lm_studio_base_url="http://localhost:1234/v1")
        client = LMStudioClient(settings)

        with patch(
            "app.lm_studio.httpx.post",
            side_effect=httpx.ConnectError("[Errno 61] Connection refused"),
        ):
            with self.assertRaises(DependencyUnavailableError) as ctx:
                client.embed(["кофе-брейк шт Питание Обед Поставщик"])

        message = str(ctx.exception)
        self.assertIn("LM Studio", message)
        self.assertIn("http://localhost:1234/v1", message)
        self.assertIn("OpenAI-compatible server", message)

    def test_lm_studio_http_error_includes_model_context(self):
        settings = Settings(
            lm_studio_base_url="http://localhost:1234/v1",
            lm_studio_embedding_model="text-embedding-nomic-embed-text-v1.5",
        )
        client = LMStudioClient(settings)
        response = httpx.Response(
            status_code=404,
            text="model not found",
            request=httpx.Request("POST", "http://localhost:1234/v1/embeddings"),
        )

        with patch("app.lm_studio.httpx.post", return_value=response):
            with self.assertRaises(DependencyUnavailableError) as ctx:
                client.embed(["тест"])

        self.assertIn("text-embedding-nomic-embed-text-v1.5", str(ctx.exception))

    def test_embedding_request_uses_configured_api_key_and_model(self):
        settings = Settings(
            embedding_base_url="https://api.vsellm.ru/v1",
            embedding_model="openai/text-embedding-3-small",
            embedding_api_key="secret-key",
        )
        client = LMStudioClient(settings)
        response = Mock()
        response.raise_for_status.return_value = None
        response.json.return_value = {"data": [{"index": 0, "embedding": [0.1, 0.2]}]}

        with patch("app.lm_studio.httpx.post", return_value=response) as post:
            self.assertEqual(client.embed(["ужин на 30 человек"]), [[0.1, 0.2]])

        _, kwargs = post.call_args
        self.assertEqual(kwargs["json"]["model"], "openai/text-embedding-3-small")
        self.assertEqual(kwargs["headers"]["Authorization"], "Bearer secret-key")
        self.assertEqual(str(post.call_args.args[0]), "https://api.vsellm.ru/v1/embeddings")

    def test_chat_request_uses_configured_api_key_endpoint_and_model(self):
        settings = Settings(
            chat_base_url="https://api.vsellm.ru/v1",
            chat_model="openai/gpt-oss-120b",
            chat_api_key="secret-key",
        )
        client = LMStudioClient(settings)
        response = Mock()
        response.raise_for_status.return_value = None
        response.json.return_value = {
            "choices": [{"message": {"content": "Готовый бриф"}}],
        }

        with patch("app.lm_studio.httpx.post", return_value=response) as post:
            self.assertEqual(client.complete("system", "user"), "Готовый бриф")

        _, kwargs = post.call_args
        self.assertEqual(str(post.call_args.args[0]), "https://api.vsellm.ru/v1/chat/completions")
        self.assertEqual(kwargs["json"]["model"], "openai/gpt-oss-120b")
        self.assertEqual(kwargs["headers"]["Authorization"], "Bearer secret-key")


if __name__ == "__main__":
    unittest.main()
