import unittest
from unittest.mock import Mock, patch

from app.auth_store import DuplicateUserError
from app.config import Settings
from app.dev_admin import create_dev_admin_user


class DevAdminTests(unittest.TestCase):
    def test_create_dev_admin_user_creates_local_admin(self):
        settings = Settings(
            database_url="postgresql://argus:argus@localhost:5432/argus",
            dev_admin_email="developer@example.com",
            dev_admin_password="developer-password",
        )
        store = Mock()
        store.create_user.return_value = {
            "id": "user-1",
            "email": "developer@example.com",
            "app_metadata": {"role": "admin"},
        }

        with patch("app.dev_admin.AuthStore", return_value=store):
            result = create_dev_admin_user(settings)

        self.assertEqual(result["id"], "user-1")
        self.assertEqual(result["email"], "developer@example.com")
        self.assertEqual(result["app_metadata"]["role"], "admin")
        store.create_user.assert_called_once_with(
            "developer@example.com",
            "developer-password",
            role="admin",
        )

    def test_create_dev_admin_user_requires_password(self):
        settings = Settings(
            database_url="postgresql://argus:argus@localhost:5432/argus",
            dev_admin_email="developer@example.com",
        )

        with self.assertRaisesRegex(ValueError, "DEV_ADMIN_PASSWORD"):
            create_dev_admin_user(settings)

    def test_create_dev_admin_user_is_idempotent_for_same_password(self):
        settings = Settings(
            database_url="postgresql://argus:argus@localhost:5432/argus",
            dev_admin_email="developer@example.com",
            dev_admin_password="developer-password",
        )
        store = Mock()
        store.create_user.side_effect = DuplicateUserError("exists")
        store.authenticate.return_value = {
            "id": "user-1",
            "email": "developer@example.com",
            "app_metadata": {"role": "admin"},
        }

        with patch("app.dev_admin.AuthStore", return_value=store):
            result = create_dev_admin_user(settings)

        self.assertEqual(result["email"], "developer@example.com")
        store.authenticate.assert_called_once_with("developer@example.com", "developer-password")

    def test_create_dev_admin_user_rejects_existing_user_with_different_password(self):
        settings = Settings(
            database_url="postgresql://argus:argus@localhost:5432/argus",
            dev_admin_email="developer@example.com",
            dev_admin_password="developer-password",
        )
        store = Mock()
        store.create_user.side_effect = DuplicateUserError("exists")
        store.authenticate.return_value = None

        with patch("app.dev_admin.AuthStore", return_value=store):
            with self.assertRaisesRegex(RuntimeError, "different password"):
                create_dev_admin_user(settings)


if __name__ == "__main__":
    unittest.main()
