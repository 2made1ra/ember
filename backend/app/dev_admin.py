from __future__ import annotations

import json
from typing import Any

import httpx

from .config import Settings, get_settings


def _require_setting(value: str | None, name: str) -> str:
    if not value:
        raise ValueError(f"{name} is required")
    return value


def _supabase_error_message(response: httpx.Response) -> str:
    try:
        payload = response.json()
    except json.JSONDecodeError:
        return response.text or response.reason_phrase

    if isinstance(payload, dict):
        for key in ("message", "msg", "error_description", "error"):
            value = payload.get(key)
            if isinstance(value, str) and value:
                return value
    return str(payload)


def create_dev_admin_user(settings: Settings | None = None) -> dict[str, Any]:
    settings = settings or get_settings()
    supabase_url = _require_setting(settings.supabase_url, "SUPABASE_URL")
    service_role_key = _require_setting(
        settings.supabase_service_role_key,
        "SUPABASE_SERVICE_ROLE_KEY",
    )
    email = _require_setting(settings.dev_admin_email, "DEV_ADMIN_EMAIL")
    password = _require_setting(settings.dev_admin_password, "DEV_ADMIN_PASSWORD")
    role = settings.dev_admin_role

    url = f"{supabase_url.rstrip('/')}/auth/v1/admin/users"
    headers = {
        "Authorization": f"Bearer {service_role_key}",
        "apikey": service_role_key,
        "Content-Type": "application/json",
    }
    payload = {
        "email": email,
        "password": password,
        "email_confirm": True,
        "app_metadata": {"role": role},
    }

    try:
        response = httpx.post(
            url,
            headers=headers,
            json=payload,
            timeout=10.0,
            trust_env=False,
        )
        response.raise_for_status()
    except httpx.HTTPStatusError as exc:
        message = _supabase_error_message(exc.response)
        raise RuntimeError(f"Supabase admin user creation failed: {message}") from exc
    except httpx.RequestError as exc:
        raise RuntimeError(f"Supabase admin API is unavailable: {exc}") from exc

    user = response.json()
    if not isinstance(user, dict) or not user.get("id"):
        raise RuntimeError("Supabase admin API returned an invalid user response")

    return {
        "id": user["id"],
        "email": user.get("email", email),
        "role": user.get("app_metadata", {}).get("role", role),
    }


def main() -> None:
    user = create_dev_admin_user()
    print(f"Created Supabase admin user {user['email']} with role {user['role']}")


if __name__ == "__main__":
    main()
