"""Keep document bodies auditable under JSON budgets; never disguise them as previews."""

import json
import re
from typing import Any

_PAGE = re.compile(r"(?m)^### \[第 (\d+) 页 / 共 (\d+) 页\]")

def _nonnegative_int(value: Any, default: int) -> int:
    return value if isinstance(value, int) and not isinstance(value, bool) and value >= 0 else default


_FIELDS = ("url", "title", "content_type", "total_pages", "extracted_pages", "start_page", "max_pages", "extract_tables", "content_offset", "window_hash", "next_read", "page_scope_note", "fetched_at", "fetch_mode", "truncated")


def _envelope(data: dict[str, Any], inherited_meta: dict[str, Any]) -> str:
    return json.dumps({"ok": True, "data": data, "meta": {**inherited_meta, "truncated": True, "reason": "正文超过预算，已保留来源与续读位置"}}, ensure_ascii=False, default=str)


def bounded_document(result: Any, budget: int, meta: dict[str, Any] | None = None) -> str | None:
    if not isinstance(result, dict) or result.get("error") or not isinstance(result.get("content"), str) or not result.get("url"):
        return None
    meta = meta if isinstance(meta, dict) else {}
    text = result["content"]
    base = {key: result[key] for key in _FIELDS if key in result}
    base["title"] = str(base.get("title") or "")[:200]
    offset = _nonnegative_int(result.get("content_offset"), 0)
    window = re.fullmatch(r"(\d+)\s*-\s*(\d+)", str(result.get("extracted_pages") or ""))
    inferred_start = int(window[1]) if window else 1
    inferred_count = max(1, int(window[2]) - inferred_start + 1) if window else 20

    def payload(length: int) -> dict[str, Any]:
        data = {**base, "content": text[:length], "content_length": len(text), "returned_characters": length, "truncated": True}
        if result.get("content_type") == "pdf":
            page_headers = list(_PAGE.finditer(text[:length]))
            if page_headers:
                data["returned_page_headers"] = [int(match[1]) for match in page_headers]
        if length < len(text) and result.get("content_type") == "pdf":
            start = _nonnegative_int(result.get("start_page"), inferred_start)
            data["next_read"] = {
                "start_page": start, "max_pages": _nonnegative_int(result.get("max_pages"), inferred_count),
                "extract_tables": bool(result.get("extract_tables", True)), "content_offset": offset + length,
            }
            if result.get("window_hash"):
                data["next_read"]["window_hash"] = result["window_hash"]
            data["continuation_note"] = "对同一URL传入next_read；content_offset是本次页窗口内偏移，不要跳过未返回内容"
        elif length < len(text):
            data["continuation_note"] = "网页正文被截断；仅返回部分可以作为证据，不代表阅读全文"
        return data

    low, high, best = 0, len(text), -1
    while low <= high:
        middle = (low + high) // 2
        if len(_envelope(payload(middle), meta or {})) <= budget:
            best = middle
            low = middle + 1
        else:
            high = middle - 1
    if best < 1:
        # Tiny context budgets must not relabel an unreadable preview as evidence.
        return "{}" if budget >= 2 else ""
    if best < len(text):
        # Prefer complete pages. A long single page uses an exact character cursor.
        boundaries = [match.start() for match in _PAGE.finditer(text) if 0 < match.start() <= best]
        if boundaries:
            best = boundaries[-1]
    return _envelope(payload(best), meta or {})
