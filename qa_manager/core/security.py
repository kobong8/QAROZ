from __future__ import annotations

import json
from typing import Any
from urllib.parse import urlparse

SENSITIVE_PARTS = (
    "authorization",
    "cookie",
    "token",
    "secret",
    "api-key",
    "apikey",
    "password",
)


def is_sensitive(key: str) -> bool:
    normalized = key.lower().replace("_", "-")
    return any(part in normalized for part in SENSITIVE_PARTS)


def redact(value: Any) -> Any:
    if isinstance(value, dict):
        return {
            key: "[REDACTED]" if is_sensitive(str(key)) else redact(item)
            for key, item in value.items()
        }
    if isinstance(value, list):
        return [redact(item) for item in value]
    return value


def protect_for_storage(value: Any) -> Any:
    """Redact secrets while retaining safe environment-variable references."""
    if isinstance(value, dict):
        return {
            key: (
                item
                if is_sensitive(str(key))
                and isinstance(item, str)
                and item.startswith("env:")
                else (
                    "[REDACTED]"
                    if is_sensitive(str(key))
                    else protect_for_storage(item)
                )
            )
            for key, item in value.items()
        }
    if isinstance(value, list):
        return [protect_for_storage(item) for item in value]
    return value


def redact_json(value: Any) -> str:
    return json.dumps(redact(value), ensure_ascii=False)


def validate_http_url(url: str, *, allow_remote: bool = True) -> str:
    parsed = urlparse(url)
    if (
        parsed.scheme not in {"http", "https"}
        or not parsed.hostname
        or parsed.username
        or parsed.password
    ):
        raise ValueError("A valid HTTP(S) URL without embedded credentials is required")
    if not allow_remote and parsed.hostname not in {"localhost", "127.0.0.1", "::1"}:
        raise ValueError("Only localhost targets are allowed")
    return url
