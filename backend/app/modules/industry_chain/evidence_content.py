"""Extract source-bound content without joining unrelated batch documents."""

import json
from dataclasses import dataclass
from typing import Any
from urllib.parse import urlsplit


@dataclass(frozen=True)
class EvidenceContent:
    text: str
    source_url: str = ""


def http_url(value: Any) -> str:
    if not isinstance(value, str):
        return ""
    try:
        parsed = urlsplit(value.strip())
        if parsed.scheme in {"http", "https"} and parsed.hostname and not parsed.username and not parsed.password:
            return value.strip()
    except ValueError:
        pass
    return ""


def extract_evidence_content(value: Any, *, structured: bool = False) -> list[EvidenceContent]:
    def walk(item: Any, parent_url: str = "") -> list[EvidenceContent]:
        if isinstance(item, list):
            return [part for child in item for part in walk(child, parent_url)]
        if not isinstance(item, dict):
            return []
        if item.get("ok") is False or item.get("error") or item.get("status") in ("error", "failed"):
            return []
        url = next((valid for key in ("url", "source_url", "final_url") if (valid := http_url(item.get(key)))), parent_url)
        if structured and not any(isinstance(item.get(key), (dict, list)) for key in ("data", "results", "items")):
            return [EvidenceContent(json.dumps(item, ensure_ascii=False, default=str), url)]
        parts = [EvidenceContent(item[key], url) for key in ("content", "text", "body", "markdown")
                 if isinstance(item.get(key), str)]
        parts.extend(part for key, child in item.items()
                     if key not in {"arguments", "request", "error", "metadata"} and isinstance(child, (dict, list))
                     for part in walk(child, url))
        return parts

    if isinstance(value, str):
        return [EvidenceContent(value)]
    return walk(value)
