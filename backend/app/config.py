from __future__ import annotations

import os
from dataclasses import dataclass
from pathlib import Path

from dotenv import load_dotenv

load_dotenv()


def _bool(name: str, default: bool = False) -> bool:
    value = os.getenv(name)
    if value is None:
        return default
    return value.strip().lower() in {"1", "true", "yes", "on"}


def _int(name: str, default: int) -> int:
    try:
        return int(os.getenv(name, str(default)))
    except ValueError:
        return default


@dataclass(frozen=True)
class Settings:
    app_env: str = os.getenv("APP_ENV", "development")
    secret_key: str = os.getenv("APP_SECRET_KEY", "semanticfit-dev-secret-change-me")
    database_url: str = os.getenv(
        "DATABASE_URL",
        "postgresql+psycopg://semanticfit:semanticfit@localhost:5432/semanticfit",
    )
    qdrant_url: str = os.getenv("QDRANT_URL", "http://localhost:6333")
    qdrant_collection: str = os.getenv("QDRANT_COLLECTION", "semanticfit_products")
    redis_url: str = os.getenv("REDIS_URL", "redis://localhost:6379/0")
    redis_enabled: bool = _bool("REDIS_ENABLED", True)

    embedding_backend: str = os.getenv("EMBEDDING_BACKEND", "bge_m3")
    embedding_model: str = os.getenv("EMBEDDING_MODEL", "BAAI/bge-m3")
    embedding_device: str = os.getenv("EMBEDDING_DEVICE", "auto")
    embedding_batch_size: int = _int("EMBEDDING_BATCH_SIZE", 128)
    embedding_dim: int = _int("EMBEDDING_DIM", 1024)
    embedding_use_fp16: bool = _bool("EMBEDDING_USE_FP16", True)

    reranker_enabled: bool = _bool("RERANKER_ENABLED", True)
    reranker_model: str = os.getenv("RERANKER_MODEL", "BAAI/bge-reranker-v2-m3")
    reranker_top_n: int = _int("RERANKER_TOP_N", 20)

    search_candidate_count: int = _int("SEARCH_CANDIDATE_COUNT", 50)
    search_default_limit: int = _int("SEARCH_DEFAULT_LIMIT", 8)
    search_max_limit: int = _int("SEARCH_MAX_LIMIT", 24)
    search_rate_limit_per_minute: int = _int("SEARCH_RATE_LIMIT_PER_MINUTE", 60)
    admin_login_rate_limit_per_minute: int = _int("ADMIN_LOGIN_RATE_LIMIT_PER_MINUTE", 10)

    llm_enabled: bool = _bool("LLM_ENABLED", False)
    llm_provider: str = os.getenv("LLM_PROVIDER", "openai")
    llm_api_key: str = os.getenv("LLM_API_KEY", "")
    llm_model: str = os.getenv("LLM_MODEL", "")
    llm_base_url: str = os.getenv("LLM_BASE_URL", "")
    llm_timeout_seconds: int = _int("LLM_TIMEOUT_SECONDS", 20)

    feedback_enabled: bool = _bool("FEEDBACK_ENABLED", True)
    audit_enabled: bool = _bool("AUDIT_ENABLED", True)

    admin_username: str = os.getenv("ADMIN_USERNAME", "admin")
    admin_password: str = os.getenv("ADMIN_PASSWORD", "admin123")

    cors_origins: str = os.getenv("CORS_ORIGINS", "http://localhost:5173,http://localhost:3000")
    session_cookie_secure: bool = _bool("SESSION_COOKIE_SECURE", False)

    reports_dir: Path = Path(os.getenv("REPORTS_DIR", "../reports")).resolve()
    data_dir: Path = Path(os.getenv("DATA_DIR", "../data")).resolve()


settings = Settings()
