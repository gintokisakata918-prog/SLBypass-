import os
from dataclasses import dataclass


def _flag(name: str, default: str = "0") -> bool:
    return os.getenv(name, default).lower() in ("1", "true", "yes", "on")


@dataclass(frozen=True)
class Settings:
    proxy_url: str | None = os.getenv("PROXY_URL") or None
    enable_browser: bool = _flag("ENABLE_BROWSER", "1")
    browser_timeout_ms: int = int(os.getenv("BROWSER_TIMEOUT_MS", "45000"))
    http_timeout_s: float = float(os.getenv("HTTP_TIMEOUT_S", "20"))
    total_budget_s: float = float(os.getenv("TOTAL_BUDGET_S", "70"))
    max_hops: int = int(os.getenv("MAX_HOPS", "8"))
    cache_ttl_s: int = int(os.getenv("CACHE_TTL_S", "600"))
    api_token: str | None = os.getenv("API_TOKEN") or None
    port: int = int(os.getenv("PORT", "8000"))


settings = Settings()
