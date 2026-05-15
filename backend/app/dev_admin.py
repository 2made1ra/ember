from __future__ import annotations

from typing import Any

from .auth_store import AuthStore, DuplicateUserError
from .config import Settings, get_settings


def _require_setting(value: str | None, name: str) -> str:
    if not value:
        raise ValueError(f"{name} is required")
    return value


def create_dev_admin_user(settings: Settings | None = None) -> dict[str, Any]:
    settings = settings or get_settings()
    email = _require_setting(settings.dev_admin_email, "DEV_ADMIN_EMAIL")
    password = _require_setting(settings.dev_admin_password, "DEV_ADMIN_PASSWORD")
    role = settings.dev_admin_role
    store = AuthStore(settings)

    try:
        return store.create_user(email, password, role=role)
    except DuplicateUserError:
        existing = store.authenticate(email, password)
        if existing:
            return existing
        raise RuntimeError("Dev admin user already exists with a different password")


def main() -> None:
    user = create_dev_admin_user()
    print(f"Created local admin user {user['email']} with role {user['app_metadata']['role']}")


if __name__ == "__main__":
    main()
