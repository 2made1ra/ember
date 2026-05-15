from __future__ import annotations

import hashlib
import hmac
import secrets
import uuid
from datetime import UTC, datetime, timedelta
from typing import Any

from .config import Settings, get_settings


PASSWORD_ITERATIONS = 210_000


class AuthStoreError(RuntimeError):
    pass


class DuplicateUserError(AuthStoreError):
    pass


def normalize_email(email: str) -> str:
    return email.strip().lower()


def hash_password(password: str) -> str:
    salt = secrets.token_hex(16)
    digest = hashlib.pbkdf2_hmac(
        "sha256",
        password.encode("utf-8"),
        salt.encode("ascii"),
        PASSWORD_ITERATIONS,
    ).hex()
    return f"pbkdf2_sha256${PASSWORD_ITERATIONS}${salt}${digest}"


def verify_password(password: str, encoded: str) -> bool:
    try:
        algorithm, iterations, salt, expected = encoded.split("$", 3)
    except ValueError:
        return False
    if algorithm != "pbkdf2_sha256":
        return False
    digest = hashlib.pbkdf2_hmac(
        "sha256",
        password.encode("utf-8"),
        salt.encode("ascii"),
        int(iterations),
    ).hex()
    return hmac.compare_digest(digest, expected)


def hash_token(token: str) -> str:
    return hashlib.sha256(token.encode("utf-8")).hexdigest()


def public_user(row: dict[str, Any]) -> dict[str, Any]:
    return {
        "id": row["id"],
        "email": row["email"],
        "app_metadata": {"role": row.get("role") or "user"},
    }


class AuthStore:
    def __init__(self, settings: Settings | None = None):
        self.settings = settings or get_settings()

    def _connect(self):
        try:
            import psycopg
            from psycopg.rows import dict_row
        except ModuleNotFoundError as exc:
            raise AuthStoreError("PostgreSQL auth driver is not installed") from exc
        return psycopg.connect(
            self.settings.database_url,
            autocommit=True,
            row_factory=dict_row,
        )

    def ensure_schema(self) -> None:
        with self._connect() as conn:
            conn.execute(
                """
                CREATE TABLE IF NOT EXISTS auth_users (
                    id TEXT PRIMARY KEY,
                    email TEXT NOT NULL UNIQUE,
                    password_hash TEXT NOT NULL,
                    role TEXT NOT NULL DEFAULT 'user',
                    created_at TIMESTAMPTZ NOT NULL DEFAULT now()
                )
                """
            )
            conn.execute(
                """
                CREATE TABLE IF NOT EXISTS auth_sessions (
                    token_hash TEXT PRIMARY KEY,
                    user_id TEXT NOT NULL REFERENCES auth_users(id) ON DELETE CASCADE,
                    expires_at TIMESTAMPTZ NOT NULL,
                    created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
                    revoked_at TIMESTAMPTZ
                )
                """
            )

    def create_user(self, email: str, password: str, role: str = "user") -> dict[str, Any]:
        self.ensure_schema()
        normalized_email = normalize_email(email)
        user = {
            "id": str(uuid.uuid4()),
            "email": normalized_email,
            "password_hash": hash_password(password),
            "role": role,
        }
        try:
            with self._connect() as conn:
                existing = conn.execute(
                    "SELECT id FROM auth_users WHERE email = %s",
                    (normalized_email,),
                ).fetchone()
                if existing:
                    raise DuplicateUserError("User already exists")
                conn.execute(
                    """
                    INSERT INTO auth_users (id, email, password_hash, role)
                    VALUES (%s, %s, %s, %s)
                    """,
                    (user["id"], user["email"], user["password_hash"], user["role"]),
                )
        except Exception as exc:
            if "unique" in str(exc).lower() or "duplicate" in str(exc).lower():
                raise DuplicateUserError("User already exists") from exc
            raise
        return public_user(user)

    def create_session(self, user: dict[str, Any]) -> dict[str, Any]:
        self.ensure_schema()
        token = secrets.token_urlsafe(32)
        expires_at = datetime.now(UTC) + timedelta(seconds=self.settings.auth_session_ttl_seconds)
        with self._connect() as conn:
            conn.execute(
                """
                INSERT INTO auth_sessions (token_hash, user_id, expires_at)
                VALUES (%s, %s, %s)
                """,
                (hash_token(token), user["id"], expires_at),
            )
        return {
            "access_token": token,
            "token_type": "bearer",
            "expires_in": self.settings.auth_session_ttl_seconds,
            "user": user,
        }

    def authenticate(self, email: str, password: str) -> dict[str, Any] | None:
        self.ensure_schema()
        with self._connect() as conn:
            row = conn.execute(
                "SELECT id, email, password_hash, role FROM auth_users WHERE email = %s",
                (normalize_email(email),),
            ).fetchone()
        if not row or not verify_password(password, row["password_hash"]):
            return None
        return public_user(row)

    def get_user_for_token(self, token: str) -> dict[str, Any] | None:
        self.ensure_schema()
        with self._connect() as conn:
            row = conn.execute(
                """
                SELECT u.id, u.email, u.role
                FROM auth_sessions s
                JOIN auth_users u ON u.id = s.user_id
                WHERE s.token_hash = %s
                  AND s.revoked_at IS NULL
                  AND s.expires_at > now()
                """,
                (hash_token(token),),
            ).fetchone()
        if not row:
            return None
        return public_user(row)

    def revoke_token(self, token: str) -> None:
        self.ensure_schema()
        with self._connect() as conn:
            conn.execute(
                "UPDATE auth_sessions SET revoked_at = now() WHERE token_hash = %s",
                (hash_token(token),),
            )


def get_auth_store() -> AuthStore:
    return AuthStore()
