"""Conservative research-body checks; these do not validate the truth of an article."""

import codecs
import re
from typing import Any

_CHARSET = re.compile(br"charset\s*=\s*[\"']?\s*([a-zA-Z0-9._-]+)", re.I)
_SHELL = ("please enable javascript", "enable javascript to continue", "请开启javascript", "请启用javascript", "请打开javascript", "javascript is required")


def decode_html_response(response: Any) -> str:
    raw = getattr(response, "content", None)
    if not isinstance(raw, bytes):
        return str(response.text)
    declared = []
    header = str(response.headers.get("content-type") or "").encode("ascii", "ignore")
    for source in (header, raw[:4096]):
        match = _CHARSET.search(source)
        if match:
            declared.append(match[1].decode("ascii"))
    # Honor declarations/valid UTF-8 before statistical guessing (GBK pages were guessed as Korean).
    candidates = [*declared, "utf-8", getattr(response, "apparent_encoding", None)]
    for encoding in candidates:
        if not encoding:
            continue
        try:
            codecs.lookup(encoding)
            return raw.decode(encoding, "strict")
        except (LookupError, UnicodeDecodeError):
            continue
    return raw.decode("utf-8", "replace")


def body_quality_reason(content: str) -> str:
    compact = re.sub(r"\s+", "", content)
    if not compact:
        return "web_empty_body"
    if len(compact) < 80:
        return "web_insufficient_body"
    if compact.count("\ufffd") / len(compact) > 0.02:
        return "web_unreadable_body"
    if sum(char.isalnum() for char in compact) < 30:
        return "web_unreadable_body"
    lower = compact.lower()
    if len(compact) < 1000 and any(re.sub(r"\s+", "", marker) in lower for marker in _SHELL):
        return "web_script_shell"
    return ""


def checked_body(result: dict[str, Any]) -> dict[str, Any]:
    if result.get("error"):
        return result
    reason = body_quality_reason(str(result.get("content") or ""))
    if not reason:
        return {**result, "body_quality": "usable"}
    return {
        "url": result.get("url", ""), "title": str(result.get("title") or "")[:200],
        "content": "", "content_type": result.get("content_type", "html"),
        "fetch_mode": result.get("fetch_mode", ""), "body_quality": "unusable",
        "error_reason": reason, "observed_characters": len(str(result.get("content") or "")),
        "error": "未获取足够可读正文（可能过短、乱码或脚本占位）；不能作为有效研究证据，请更换原文链接或使用浏览器模式",
    }
