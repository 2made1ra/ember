import unittest
from unittest.mock import Mock, patch

import httpx

from app.config import Settings
from app.dev_admin import create_dev_admin_user


class DevAdminTests(unittest.TestCase):
    def test_create_dev_admin_user_posts_supabase_admin_payload(self):
        settings = Settings(
            supabase_url="https://project-ref.supabase.co",
            supabase_service_role_key="service-role-key",
            dev_admin_email="developer@example.com",
            dev_admin_password="developer-password",
        )
        supabase_response = Mock()
        supabase_response.raise_for_status.return_value = None
        supabase_response.json.return_value = {
            "id": "user-1",
            "email": "developer@example.com",
            "app_metadata": {"role": "admin"},
        }

        with patch("app.dev_admin.httpx.post", return_value=supabase_response) as post:
            result = create_dev_admin_user(settings)

        self.assertEqual(result["id"], "user-1")
        self.assertEqual(result["email"], "developer@example.com")
        self.assertEqual(result["role"], "admin")
        self.assertEqual(str(post.call_args.args[0]), "https://project-ref.supabase.co/auth/v1/admin/users")
        self.assertIs(post.call_args.kwargs["trust_env"], False)
        self.assertEqual(
            post.call_args.kwargs["headers"],
            {
                "Authorization": "Bearer service-role-key",
                "apikey": "service-role-key",
                "Content-Type": "application/json",
            },
        )
        self.assertEqual(
            post.call_args.kwargs["json"],
            {
                "email": "developer@example.com",
                "password": "developer-password",
                "email_confirm": True,
                "app_metadata": {"role": "admin"},
            },
        )

    def test_create_dev_admin_user_requires_service_role_key(self):
        settings = Settings(
            supabase_url="https://project-ref.supabase.co",
            dev_admin_email="developer@example.com",
            dev_admin_password="developer-password",
        )

        with self.assertRaisesRegex(ValueError, "SUPABASE_SERVICE_ROLE_KEY"):
            create_dev_admin_user(settings)

    def test_create_dev_admin_user_raises_clear_message_for_supabase_error(self):
        settings = Settings(
            supabase_url="https://project-ref.supabase.co",
            supabase_service_role_key="service-role-key",
            dev_admin_email="developer@example.com",
            dev_admin_password="developer-password",
        )
        request = httpx.Request("POST", "https://project-ref.supabase.co/auth/v1/admin/users")
        response = httpx.Response(
            status_code=422,
            json={"msg": "A user with this email address has already been registered"},
            request=request,
        )

        with patch(
            "app.dev_admin.httpx.post",
            side_effect=httpx.HTTPStatusError("Unprocessable Entity", request=request, response=response),
        ):
            with self.assertRaisesRegex(RuntimeError, "already been registered"):
                create_dev_admin_user(settings)


if __name__ == "__main__":
    unittest.main()
