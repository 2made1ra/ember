from __future__ import annotations

import os
from dataclasses import dataclass, field


def env_str(name: str, default: str) -> str:
    return os.getenv(name, default)


def env_optional(name: str) -> str | None:
    return os.getenv(name)


def env_first(names: tuple[str, ...]) -> str | None:
    for name in names:
        value = os.getenv(name)
        if value:
            return value
    return None


def default_embedding_base_url() -> str:
    configured = env_first(("EMBEDDING_BASE_URL", "OPENAI_BASE_URL"))
    if configured:
        return configured
    if env_first(("API_KEY", "OPENAI_API_KEY")):
        return "https://api.vsellm.ru/v1"
    return env_str("LM_STUDIO_BASE_URL", "http://localhost:1234/v1")


def default_embedding_model() -> str:
    configured = env_first(("EMBEDDING_MODEL",))
    if configured:
        return configured
    if env_first(("API_KEY", "OPENAI_API_KEY")):
        return "openai/text-embedding-3-small"
    return env_str("LM_STUDIO_EMBEDDING_MODEL", "text-embedding-nomic-embed-text-v1.5")


def default_chat_base_url() -> str:
    configured = env_first(("CHAT_BASE_URL", "OPENAI_BASE_URL"))
    if configured:
        return configured
    if env_first(("API_KEY", "OPENAI_API_KEY")):
        return "https://api.vsellm.ru/v1"
    return env_str("LM_STUDIO_BASE_URL", "http://localhost:1234/v1")


def default_chat_model() -> str:
    configured = env_first(("CHAT_MODEL",))
    if configured:
        return configured
    if env_first(("API_KEY", "OPENAI_API_KEY")):
        return "openai/gpt-oss-120b"
    return env_str("LM_STUDIO_CHAT_MODEL", "local-model")


@dataclass(frozen=True)
class Settings:
    lm_studio_base_url: str = field(
        default_factory=lambda: env_str("LM_STUDIO_BASE_URL", "http://localhost:1234/v1")
    )
    lm_studio_embedding_model: str = field(
        default_factory=lambda: env_str(
            "LM_STUDIO_EMBEDDING_MODEL",
            "text-embedding-nomic-embed-text-v1.5",
        )
    )
    lm_studio_chat_model: str = field(
        default_factory=lambda: env_str("LM_STUDIO_CHAT_MODEL", "local-model")
    )
    embedding_base_url: str = field(default_factory=default_embedding_base_url)
    embedding_model: str = field(default_factory=default_embedding_model)
    embedding_api_key: str | None = field(
        default_factory=lambda: env_first(("API_KEY", "OPENAI_API_KEY", "EMBEDDING_API_KEY"))
    )
    chat_base_url: str = field(default_factory=default_chat_base_url)
    chat_model: str = field(default_factory=default_chat_model)
    chat_api_key: str | None = field(
        default_factory=lambda: env_first(("CHAT_API_KEY", "API_KEY", "OPENAI_API_KEY"))
    )
    qdrant_url: str = field(default_factory=lambda: env_str("QDRANT_URL", "http://localhost:6333"))
    qdrant_api_key: str | None = field(default_factory=lambda: env_optional("QDRANT_API_KEY"))
    qdrant_collection: str = field(
        default_factory=lambda: env_str("QDRANT_COLLECTION", "argus_price_items")
    )
    supabase_url: str | None = field(default_factory=lambda: env_optional("SUPABASE_URL"))
    supabase_publishable_key: str | None = field(
        default_factory=lambda: env_optional("SUPABASE_PUBLISHABLE_KEY")
    )
    supabase_service_role_key: str | None = field(
        default_factory=lambda: env_optional("SUPABASE_SERVICE_ROLE_KEY")
    )
    dev_admin_email: str | None = field(default_factory=lambda: env_optional("DEV_ADMIN_EMAIL"))
    dev_admin_password: str | None = field(default_factory=lambda: env_optional("DEV_ADMIN_PASSWORD"))
    dev_admin_role: str = field(default_factory=lambda: env_str("DEV_ADMIN_ROLE", "admin"))


def get_settings() -> Settings:
    return Settings()
