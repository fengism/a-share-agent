"""Presentation-only replacement of internal references; never mutate audit data."""
from __future__ import annotations

import re
from typing import Any

_REF = re.compile(r"(?:证据(?:\s*ID)?\s*[:：]?\s*)?`?(?<![a-z0-9_])(ev_[a-z0-9_-]+)(?![a-z0-9_])`?", re.I)
_URL = re.compile(r"https?://[^\s<>\"')\]]+", re.I)
_ID_FIELDS = {"evidence_id", "evidence_ids", "summary_evidence_ids", "positioning_evidence_ids"}
_URL_FIELDS = {"url", "source_url", "source_urls", "pdf_url", "href"}


def reference_labels(catalog: list[dict]) -> dict[str, str]:
    return {str(item.get("evidence_id", "")).lower(): f"资料 {index + 1}"
            for index, item in enumerate(catalog) if item.get("evidence_id")}


def readable_references(text: str, labels: dict[str, str] | None = None) -> str:
    labels = labels or {}
    # Preserve destinations, including opaque URL identifiers beginning ev_.
    parts = []
    offset = 0
    for match in _URL.finditer(text):
        parts.append(_REF.sub(lambda ref: labels.get(ref[1].lower(), "相关资料"), text[offset:match.start()]))
        parts.append(match[0])
        offset = match.end()
    parts.append(_REF.sub(lambda ref: labels.get(ref[1].lower(), "相关资料"), text[offset:]))
    return "".join(parts)


def presentation_payload(value: Any) -> Any:
    """A throwaway render copy with readable citation labels, not for persistence/validation."""
    payload = value.model_dump() if hasattr(value, "model_dump") else value
    labels = reference_labels(payload.get("evidence_catalog", [])) if isinstance(payload, dict) else {}

    def walk(item, key=""):
        if key in _URL_FIELDS:
            return item
        if isinstance(item, str):
            if key in _ID_FIELDS:
                return labels.get(item.lower(), "相关资料")
            return readable_references(item, labels)
        if isinstance(item, list):
            return [walk(child, key) for child in item]
        if isinstance(item, dict):
            return {field: walk(child, field) for field, child in item.items()}
        return item

    return walk(payload)
