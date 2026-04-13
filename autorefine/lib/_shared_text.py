from __future__ import annotations

from datetime import datetime, timezone
import re
from typing import Any


_IDENTIFIER_PATTERN = re.compile(r"[^a-z0-9]+")


def clean_text(value: Any, *, default: str = "") -> str:
    if value is None:
        return default
    if isinstance(value, str):
        return value.strip()
    return str(value).strip()


def clean_identifier(value: Any, *, default: str = "") -> str:
    cleaned = clean_text(value, default=default).lower()
    if not cleaned:
        return default
    return _IDENTIFIER_PATTERN.sub("_", cleaned).strip("_") or default


def now_utc_timestamp() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")
