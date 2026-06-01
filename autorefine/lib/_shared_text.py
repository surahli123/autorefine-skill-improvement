from __future__ import annotations

from collections.abc import Mapping
from datetime import datetime, timezone
import hashlib
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


def _sha256_text(value: str) -> str:
    return f"sha256:{hashlib.sha256(value.encode('utf-8')).hexdigest()}"


def _first_present(mapping: Mapping[str, Any], *keys: str) -> Any:
    for key in keys:
        if key in mapping and mapping[key] is not None:
            return mapping[key]
    return None


def _coerce_numeric(value: Any) -> float | None:
    if value is None or isinstance(value, bool):
        return None
    if isinstance(value, (int, float)):
        return float(value)

    normalized = clean_text(value)
    if not normalized:
        return None
    try:
        return float(normalized)
    except ValueError:
        return None


def _mapping_or_empty(value: Any) -> Mapping[str, Any]:
    return value if isinstance(value, Mapping) else {}
