from __future__ import annotations

import hashlib
import re
from bisect import bisect_right
from collections.abc import Callable, Mapping
from dataclasses import dataclass
from html.parser import HTMLParser
from typing import Any

from ._shared_text import (
    clean_identifier as _clean_identifier,
    clean_text as _clean_text,
    now_utc_timestamp as _now_utc_timestamp,
)


SOURCE_DOCUMENT_SCHEMA_VERSION = 1
SOURCE_PARSER_CONTRACT_VERSION = 1
CANONICAL_SOURCE_DOCUMENT_TYPE = "normalized_source_document"
CANONICAL_SOURCE_PARSER_ADAPTERS = ("text", "markdown", "html")

_MEDIA_TYPE_TO_ADAPTER = {
    "text/plain": "text",
    "text/markdown": "markdown",
    "text/x-markdown": "markdown",
    "text/html": "html",
    "application/xhtml+xml": "html",
}
_EXTENSION_TO_ADAPTER = {
    ".txt": "text",
    ".md": "markdown",
    ".markdown": "markdown",
    ".html": "html",
    ".htm": "html",
    ".xhtml": "html",
}
_MARKDOWN_HEADING_PATTERN = re.compile(r"^(#{1,6})\s+(.+?)\s*$", re.MULTILINE)
_WHITESPACE_PATTERN = re.compile(r"\s+")


class SourceParserAdapterError(ValueError):
    """Raised when parser adapter resolution or normalization fails."""


@dataclass(frozen=True)
class ParserAdapterContract:
    """Stable parser adapter contract used by all source-document adapters."""

    adapter_id: str
    display_name: str
    supported_media_types: tuple[str, ...]
    supported_extensions: tuple[str, ...]


_ADAPTER_CONTRACTS: dict[str, ParserAdapterContract] = {
    "text": ParserAdapterContract(
        adapter_id="text",
        display_name="Plain Text Parser",
        supported_media_types=("text/plain",),
        supported_extensions=(".txt",),
    ),
    "markdown": ParserAdapterContract(
        adapter_id="markdown",
        display_name="Markdown Parser",
        supported_media_types=("text/markdown", "text/x-markdown"),
        supported_extensions=(".md", ".markdown"),
    ),
    "html": ParserAdapterContract(
        adapter_id="html",
        display_name="HTML Parser",
        supported_media_types=("text/html", "application/xhtml+xml"),
        supported_extensions=(".html", ".htm", ".xhtml"),
    ),
}


def _normalize_newlines(text: str) -> str:
    normalized = text.replace("\r\n", "\n").replace("\r", "\n")
    if not normalized:
        return ""
    return normalized.rstrip("\n") + "\n"


def _sha256_text(value: str) -> str:
    return f"sha256:{hashlib.sha256(value.encode('utf-8')).hexdigest()}"


def _line_start_offsets(text: str) -> list[int]:
    line_starts = [0]
    for match in re.finditer(r"\n", text):
        next_offset = match.end()
        if next_offset < len(text):
            line_starts.append(next_offset)
    return line_starts


def _line_number_for_offset(line_starts: list[int], offset: int) -> int:
    if not line_starts:
        return 1
    bounded_offset = max(offset, 0)
    return max(1, bisect_right(line_starts, bounded_offset))


def _line_end_for_span(text: str, line_starts: list[int], start: int, end: int) -> int:
    if end <= start:
        return _line_number_for_offset(line_starts, start)

    trimmed_end = end
    while trimmed_end > start and text[trimmed_end - 1] == "\n":
        trimmed_end -= 1

    if trimmed_end <= start:
        return _line_number_for_offset(line_starts, start)
    return _line_number_for_offset(line_starts, trimmed_end - 1)


def _byte_offset(text: str, char_offset: int) -> int:
    return len(text[:char_offset].encode("utf-8"))


def _collapse_whitespace(value: str) -> str:
    return _WHITESPACE_PATTERN.sub(" ", value).strip()


def _guess_extension(location: str) -> str:
    lowered = location.lower()
    for extension in _EXTENSION_TO_ADAPTER:
        if lowered.endswith(extension):
            return extension
    return ""


def _resolve_adapter(
    *,
    adapter_hint: str | None,
    media_type: str | None,
    location: str,
) -> str:
    normalized_hint = _clean_text(adapter_hint).lower()
    if normalized_hint:
        if normalized_hint not in CANONICAL_SOURCE_PARSER_ADAPTERS:
            raise SourceParserAdapterError(
                f"unsupported parser adapter hint {adapter_hint!r}; expected one of {CANONICAL_SOURCE_PARSER_ADAPTERS}"
            )
        return normalized_hint

    normalized_media_type = _clean_text(media_type).lower()
    if normalized_media_type:
        adapter_from_media_type = _MEDIA_TYPE_TO_ADAPTER.get(normalized_media_type)
        if adapter_from_media_type is not None:
            return adapter_from_media_type

    extension = _guess_extension(location)
    if extension:
        adapter_from_extension = _EXTENSION_TO_ADAPTER.get(extension)
        if adapter_from_extension is not None:
            return adapter_from_extension

    return "text"


def _iso_timestamp_or_default(value: Any) -> str:
    normalized = _clean_text(value)
    if not normalized:
        return _now_utc_timestamp()

    try:
        datetime.fromisoformat(normalized.replace("Z", "+00:00"))
    except ValueError as exc:
        raise SourceParserAdapterError(f"retrieved_at must be an ISO timestamp; received {value!r}") from exc
    return normalized


def _build_section(
    *,
    normalized_text: str,
    section_id: str,
    section_kind: str,
    heading: str | None,
    heading_level: int | None,
    order: int,
    start: int,
    end: int,
    source_locator_base: Mapping[str, Any],
) -> dict[str, Any]:
    line_starts = _line_start_offsets(normalized_text)
    text = normalized_text[start:end]
    line_start = _line_number_for_offset(line_starts, start)
    line_end = _line_end_for_span(normalized_text, line_starts, start, end)

    source_locator = {
        "path": source_locator_base.get("path"),
        "media_type": source_locator_base.get("media_type"),
        "adapter_id": source_locator_base.get("adapter_id"),
        "offset_basis": "normalized_text_utf8",
        "section_id": section_id,
        "line_start": line_start,
        "line_end": line_end,
    }

    return {
        "section_id": section_id,
        "section_kind": section_kind,
        "order": order,
        "heading": heading,
        "heading_level": heading_level,
        "text": text,
        "content_hash": _sha256_text(text),
        "char_start": start,
        "char_end": end,
        "byte_start": _byte_offset(normalized_text, start),
        "byte_end": _byte_offset(normalized_text, end),
        "line_start": line_start,
        "line_end": line_end,
        "source_locator": source_locator,
    }


def _parse_text_adapter(
    normalized_text: str,
    *,
    source_locator_base: Mapping[str, Any],
) -> dict[str, Any]:
    has_content = bool(normalized_text.strip())
    sections = []
    if has_content:
        sections.append(
            _build_section(
                normalized_text=normalized_text,
                section_id="document",
                section_kind="document",
                heading=None,
                heading_level=None,
                order=1,
                start=0,
                end=len(normalized_text),
                source_locator_base=source_locator_base,
            )
        )

    return {
        "title": "",
        "sections": sections,
        "parsing_notes": {
            "has_headings": False,
            "heading_count": 0,
            "normalization_mode": "plain_text_document",
        },
    }


def _parse_markdown_adapter(
    normalized_text: str,
    *,
    source_locator_base: Mapping[str, Any],
) -> dict[str, Any]:
    heading_matches = list(_MARKDOWN_HEADING_PATTERN.finditer(normalized_text))
    sections: list[dict[str, Any]] = []
    section_id_counts: dict[str, int] = {}

    def unique_section_id(base: str) -> str:
        count = section_id_counts.get(base, 0) + 1
        section_id_counts[base] = count
        return base if count == 1 else f"{base}__{count}"

    if not heading_matches:
        return {
            "title": "",
            "sections": [
                _build_section(
                    normalized_text=normalized_text,
                    section_id="document",
                    section_kind="document",
                    heading=None,
                    heading_level=None,
                    order=1,
                    start=0,
                    end=len(normalized_text),
                    source_locator_base=source_locator_base,
                )
            ]
            if normalized_text.strip()
            else [],
            "parsing_notes": {
                "has_headings": False,
                "heading_count": 0,
                "normalization_mode": "markdown_no_headings",
            },
        }

    first_heading_start = heading_matches[0].start()
    if first_heading_start > 0 and normalized_text[:first_heading_start].strip():
        sections.append(
            _build_section(
                normalized_text=normalized_text,
                section_id="preamble",
                section_kind="preamble",
                heading=None,
                heading_level=None,
                order=1,
                start=0,
                end=first_heading_start,
                source_locator_base=source_locator_base,
            )
        )

    for index, match in enumerate(heading_matches):
        heading_level = len(match.group(1))
        heading_text = match.group(2).strip()
        base_id = _clean_identifier(heading_text, default=f"section_{index + 1}") or f"section_{index + 1}"
        section_id = unique_section_id(base_id)
        end = heading_matches[index + 1].start() if index + 1 < len(heading_matches) else len(normalized_text)

        sections.append(
            _build_section(
                normalized_text=normalized_text,
                section_id=section_id,
                section_kind="section",
                heading=heading_text,
                heading_level=heading_level,
                order=len(sections) + 1,
                start=match.start(),
                end=end,
                source_locator_base=source_locator_base,
            )
        )

    title = heading_matches[0].group(2).strip() if heading_matches else ""
    return {
        "title": title,
        "sections": sections,
        "parsing_notes": {
            "has_headings": True,
            "heading_count": len(heading_matches),
            "normalization_mode": "markdown_headings",
        },
    }


class _HtmlSectionParser(HTMLParser):
    def __init__(self) -> None:
        super().__init__(convert_charrefs=True)
        self._skip_depth = 0
        self._within_heading_tag: str | None = None
        self._heading_start_offset: int | None = None
        self._heading_buffer: list[str] = []
        self._chunks: list[str] = []
        self.headings: list[dict[str, Any]] = []
        self.title = ""
        self._capture_title = False
        self._title_buffer: list[str] = []

    def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        normalized_tag = tag.lower()
        if normalized_tag in {"script", "style", "noscript"}:
            self._skip_depth += 1
            return
        if self._skip_depth:
            return

        if normalized_tag == "title":
            self._capture_title = True
            self._title_buffer = []
            return

        if re.fullmatch(r"h[1-6]", normalized_tag):
            self._within_heading_tag = normalized_tag
            self._heading_start_offset = len("".join(self._chunks))
            self._heading_buffer = []
            return

        if normalized_tag in {"p", "li", "br", "div", "section", "article", "header", "footer", "main", "aside"}:
            self._chunks.append("\n")

    def handle_endtag(self, tag: str) -> None:
        normalized_tag = tag.lower()
        if normalized_tag in {"script", "style", "noscript"}:
            if self._skip_depth:
                self._skip_depth -= 1
            return
        if self._skip_depth:
            return

        if normalized_tag == "title":
            self._capture_title = False
            self.title = _collapse_whitespace("".join(self._title_buffer))
            return

        if self._within_heading_tag == normalized_tag:
            heading_text = _collapse_whitespace("".join(self._heading_buffer))
            if heading_text:
                self.headings.append(
                    {
                        "text": heading_text,
                        "level": int(normalized_tag[1]),
                        "start": self._heading_start_offset or 0,
                    }
                )
            self._within_heading_tag = None
            self._heading_start_offset = None
            self._heading_buffer = []
            self._chunks.append("\n")
            return

        if normalized_tag in {"p", "li", "div", "section", "article", "header", "footer", "main", "aside"}:
            self._chunks.append("\n")

    def handle_data(self, data: str) -> None:
        if self._skip_depth:
            return
        if self._capture_title:
            self._title_buffer.append(data)
        if not data:
            return

        normalized = _collapse_whitespace(data)
        if not normalized:
            return

        if self._within_heading_tag is not None:
            self._heading_buffer.append(normalized + " ")

        self._chunks.append(normalized)
        self._chunks.append("\n")

    def as_text(self) -> str:
        joined = "".join(self._chunks)
        lines = [line.strip() for line in joined.splitlines()]
        collapsed = "\n".join(line for line in lines if line)
        return _normalize_newlines(collapsed)


def _parse_html_adapter(
    normalized_text: str,
    *,
    source_locator_base: Mapping[str, Any],
) -> dict[str, Any]:
    parser = _HtmlSectionParser()
    parser.feed(normalized_text)
    parser.close()

    text_content = parser.as_text()
    if not text_content:
        return {
            "title": parser.title,
            "sections": [],
            "normalized_text": "",
            "parsing_notes": {
                "has_headings": False,
                "heading_count": 0,
                "normalization_mode": "html_empty",
            },
        }

    raw_headings = parser.headings
    headings: list[dict[str, Any]] = []
    search_cursor = 0
    for heading in raw_headings:
        heading_text = _clean_text(heading.get("text"))
        if not heading_text:
            continue
        resolved_start = text_content.find(heading_text, search_cursor)
        if resolved_start < 0:
            resolved_start = text_content.find(heading_text)
        if resolved_start < 0:
            continue
        search_cursor = resolved_start + len(heading_text)
        headings.append(
            {
                "text": heading_text,
                "level": int(heading.get("level", 1)),
                "start": resolved_start,
            }
        )
    sections: list[dict[str, Any]] = []
    section_id_counts: dict[str, int] = {}

    def unique_section_id(base: str) -> str:
        count = section_id_counts.get(base, 0) + 1
        section_id_counts[base] = count
        return base if count == 1 else f"{base}__{count}"

    if not headings:
        sections.append(
            _build_section(
                normalized_text=text_content,
                section_id="document",
                section_kind="document",
                heading=None,
                heading_level=None,
                order=1,
                start=0,
                end=len(text_content),
                source_locator_base=source_locator_base,
            )
        )
    else:
        first_heading_start = headings[0]["start"]
        if first_heading_start > 0 and text_content[:first_heading_start].strip():
            sections.append(
                _build_section(
                    normalized_text=text_content,
                    section_id="preamble",
                    section_kind="preamble",
                    heading=None,
                    heading_level=None,
                    order=1,
                    start=0,
                    end=first_heading_start,
                    source_locator_base=source_locator_base,
                )
            )

        for index, heading in enumerate(headings):
            heading_text = _clean_text(heading.get("text"))
            base_id = _clean_identifier(heading_text, default=f"section_{index + 1}") or f"section_{index + 1}"
            section_id = unique_section_id(base_id)
            start = int(heading.get("start", 0))
            end = int(headings[index + 1]["start"]) if index + 1 < len(headings) else len(text_content)

            sections.append(
                _build_section(
                    normalized_text=text_content,
                    section_id=section_id,
                    section_kind="section",
                    heading=heading_text,
                    heading_level=int(heading.get("level", 1)),
                    order=len(sections) + 1,
                    start=start,
                    end=end,
                    source_locator_base=source_locator_base,
                )
            )

    title = parser.title or (headings[0]["text"] if headings else "")
    return {
        "title": title,
        "sections": sections,
        "normalized_text": text_content,
        "parsing_notes": {
            "has_headings": bool(headings),
            "heading_count": len(headings),
            "normalization_mode": "html_text_projection",
        },
    }


_ADAPTER_HANDLERS: dict[str, Callable[..., dict[str, Any]]] = {
    "text": _parse_text_adapter,
    "markdown": _parse_markdown_adapter,
    "html": _parse_html_adapter,
}


def list_source_parser_adapter_contracts() -> list[dict[str, Any]]:
    """Return parser adapter contracts in a stable, serializable format."""

    return [
        {
            "adapter_id": contract.adapter_id,
            "display_name": contract.display_name,
            "supported_media_types": list(contract.supported_media_types),
            "supported_extensions": list(contract.supported_extensions),
            "contract_version": SOURCE_PARSER_CONTRACT_VERSION,
        }
        for contract in _ADAPTER_CONTRACTS.values()
    ]


def parse_source_document(
    source_document: str,
    *,
    source_id: str,
    location: str,
    media_type: str | None = None,
    adapter_hint: str | None = None,
    retrieved_at: str | None = None,
    metadata: Mapping[str, Any] | None = None,
) -> dict[str, Any]:
    """Parse a source document through adapter contracts into one normalized schema.

    Adapter-specific extraction details are retained in `parsing_notes`, while
    downstream consumers use the shared schema boundary (`document`, `sections`,
    offsets, hashes, and source locator metadata) regardless of adapter type.
    """

    normalized_source_id = _clean_identifier(source_id)
    if not normalized_source_id:
        raise SourceParserAdapterError("source_id is required")

    normalized_location = _clean_text(location)
    if not normalized_location:
        raise SourceParserAdapterError("location is required")

    adapter_id = _resolve_adapter(
        adapter_hint=adapter_hint,
        media_type=media_type,
        location=normalized_location,
    )

    parser = _ADAPTER_HANDLERS[adapter_id]
    contract = _ADAPTER_CONTRACTS[adapter_id]

    normalized_input = _normalize_newlines(source_document)
    normalized_media_type = _clean_text(media_type) or None
    if normalized_media_type is None and contract.supported_media_types:
        normalized_media_type = contract.supported_media_types[0]

    source_locator_base = {
        "path": normalized_location,
        "media_type": normalized_media_type,
        "adapter_id": adapter_id,
    }

    parsed = parser(
        normalized_input,
        source_locator_base=source_locator_base,
    )

    normalized_text = _normalize_newlines(
        _clean_text(parsed.get("normalized_text")) if "normalized_text" in parsed else normalized_input
    )
    title = _clean_text(parsed.get("title"))
    sections = parsed.get("sections")
    if not isinstance(sections, list):
        raise SourceParserAdapterError(f"{adapter_id} adapter must return sections as a list")

    document_excerpt = "\n".join(line for line in normalized_text.splitlines()[:3]).strip()
    metadata_payload = dict(metadata) if isinstance(metadata, Mapping) else {}

    return {
        "schema_version": SOURCE_DOCUMENT_SCHEMA_VERSION,
        "bundle_type": CANONICAL_SOURCE_DOCUMENT_TYPE,
        "parser_contract_version": SOURCE_PARSER_CONTRACT_VERSION,
        "source_id": normalized_source_id,
        "adapter_id": adapter_id,
        "adapter_contract": {
            "adapter_id": contract.adapter_id,
            "display_name": contract.display_name,
            "supported_media_types": list(contract.supported_media_types),
            "supported_extensions": list(contract.supported_extensions),
            "contract_version": SOURCE_PARSER_CONTRACT_VERSION,
        },
        "source_ref": {
            "location": normalized_location,
            "media_type": normalized_media_type,
            "extension": _guess_extension(normalized_location) or None,
            "retrieved_at": _iso_timestamp_or_default(retrieved_at),
        },
        "document": {
            "title": title,
            "summary": document_excerpt,
            "normalized_text": normalized_text,
            "char_count": len(normalized_text),
            "line_count": len(normalized_text.splitlines()),
            "content_hash": _sha256_text(normalized_text),
        },
        "sections": sections,
        "section_count": len(sections),
        "parsing_notes": {
            **(parsed.get("parsing_notes") if isinstance(parsed.get("parsing_notes"), Mapping) else {}),
            "adapter_boundary_normalized": True,
        },
        "metadata": metadata_payload,
    }


__all__ = [
    "CANONICAL_SOURCE_DOCUMENT_TYPE",
    "CANONICAL_SOURCE_PARSER_ADAPTERS",
    "SOURCE_DOCUMENT_SCHEMA_VERSION",
    "SOURCE_PARSER_CONTRACT_VERSION",
    "SourceParserAdapterError",
    "list_source_parser_adapter_contracts",
    "parse_source_document",
]
