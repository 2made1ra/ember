from __future__ import annotations

from typing import Any

from fastapi import HTTPException, Security, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer

from .auth_store import AuthStoreError, get_auth_store


bearer_scheme = HTTPBearer(auto_error=False)


def bearer_token(
    credentials: HTTPAuthorizationCredentials | None = Security(bearer_scheme),
) -> str:
    if credentials is None or credentials.scheme.lower() != "bearer" or not credentials.credentials:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Authorization bearer token is required",
        )
    return credentials.credentials


def require_user(token: str = Security(bearer_token)) -> dict[str, Any]:
    try:
        user = get_auth_store().get_user_for_token(token)
    except AuthStoreError as exc:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail=str(exc),
        ) from exc
    except Exception as exc:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="PostgreSQL auth is unavailable",
        ) from exc

    if not user:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid bearer token",
        )
    return user
