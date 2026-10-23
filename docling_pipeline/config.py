from __future__ import annotations

import os
from dataclasses import dataclass
from typing import Mapping, Optional


class ConfigError(RuntimeError):
    """Raised when the environment configuration is missing or invalid."""


def _int(env: Mapping[str, str], name: str, default: int) -> int:
    raw = env.get(name)
    if raw is None or raw == "":
        return default
    try:
        value = int(raw)
    except ValueError as exc:
        raise ConfigError(f"{name} must be an integer") from exc
    if value <= 0:
        raise ConfigError(f"{name} must be > 0")
    return value


@dataclass(frozen=True)
class Config:
    n8n_base_url: str
    n8n_token: str
    wake_timeout_s: int = 300
    wake_interval_s: int = 10
    status_timeout_s: int = 2400
    status_interval_s: int = 60
    request_timeout_s: int = 30
    download_timeout_s: int = 120
    max_pdf_mb: int = 50
    max_docs_per_run: int = 10
    do_ocr: bool = False

    @classmethod
    def from_env(cls, env: Optional[Mapping[str, str]] = None) -> "Config":
        env = os.environ if env is None else env
        missing = [k for k in ("N8N_BASE_URL", "N8N_TOKEN") if not env.get(k)]
        if missing:
            raise ConfigError("missing required environment variables: " + ", ".join(missing))
        return cls(
            n8n_base_url=env["N8N_BASE_URL"].rstrip("/"),
            n8n_token=env["N8N_TOKEN"],
            wake_timeout_s=_int(env, "WAKE_TIMEOUT_S", 300),
            wake_interval_s=_int(env, "WAKE_INTERVAL_S", 10),
            status_timeout_s=_int(env, "STATUS_TIMEOUT_S", 2400),
            status_interval_s=_int(env, "STATUS_INTERVAL_S", 60),
            request_timeout_s=_int(env, "REQUEST_TIMEOUT_S", 30),
            download_timeout_s=_int(env, "DOWNLOAD_TIMEOUT_S", 120),
            max_pdf_mb=_int(env, "MAX_PDF_MB", 50),
            max_docs_per_run=_int(env, "MAX_DOCS_PER_RUN", 10),
            do_ocr=env.get("DO_OCR", "false").strip().lower() in {"1", "true", "yes"},
        )
