"""Select literal source-bound windows; never summarize or re-key evidence."""

from __future__ import annotations

import json
import re

from app.agentic.contracts import AgentEvidence, agent_evidence_id
from app.agentic.tools.serialization import serialize_context_result
from app.modules.industry_chain.evidence_content import extract_evidence_content

# Include counter-evidence explicitly; relevance must not mean optimism only.
_DEFAULT_TERMS = (
    "订单",
    "交付",
    "验收",
    "成本",
    "毛利",
    "库存",
    "现金流",
    "回款",
    "产能",
    "良率",
    "客户",
    "需求",
    "采购",
    "价格",
    "利用率",
    "动销",
    "临床",
    "获批",
    "取消",
    "延期",
    "下滑",
    "亏损",
    "未形成",
    "未披露",
    "减值",
    "风险",
    "不及预期",
)
_NEGATIVE_TERMS = ("取消", "延期", "下滑", "亏损", "未形成", "未披露", "减值", "风险", "不及预期")
_WINDOW = 560
_OVERLAP = 100


def _decode(content: str):
    try:
        return json.loads(content)
    except (TypeError, ValueError):
        return {}


def _windows(text: str, focus_terms: tuple[str, ...]):
    candidates = []
    # Windows are contiguous original slices; selection is not semantic fact verification.
    for start in range(0, len(text), _WINDOW - _OVERLAP):
        end = min(len(text), start + _WINDOW)
        # Keep the surrounding sentence where practical, so "未/但" is not dropped
        # simply because it was one character outside the fixed window boundary.
        left = list(re.finditer(r"[。！？!?\n]", text[max(0, start - 160) : start]))
        start = max(0, start - 160) + left[-1].end() if left else max(0, start - 160)
        right = re.search(r"[。！？!?\n]", text[end : min(len(text), end + 160)])
        end = end + right.end() if right else min(len(text), end + 160)
        quote = text[start:end]
        lowered = quote.lower()
        score = sum(term in lowered for term in _DEFAULT_TERMS)
        score += sum(4 for term in focus_terms if term.lower() in lowered)
        negative = any(term in quote for term in _NEGATIVE_TERMS)
        candidates.append((score, negative, start, end))
    ranked = sorted(candidates, key=lambda item: (-item[0], item[2]))
    # Lead with most relevant evidence, reserve a high-ranking contrary window if present.
    ordered = ranked[:1]
    contrary = next((item for item in ranked if item[1] and item not in ordered), None)
    if contrary is not None:
        ordered.append(contrary)
    ordered.extend(item for item in ranked if item not in ordered)
    selected = []
    for score, negative, start, end in ordered:
        if any(start < old_end and end > old_start for old_start, old_end in selected):
            continue
        selected.append((start, end))
        yield {"start": start, "end": end, "quote": text[start:end]}
        if len(selected) >= 8:
            break


def _body_payload(item: AgentEvidence, budget: int, focus_terms: tuple[str, ...]) -> str | None:
    parts = extract_evidence_content(_decode(item.content))
    unique = list(
        {(part.source_url, part.text): part for part in parts if part.source_url and part.text.strip()}.values()
    )
    if not unique:
        return None
    records = []
    pools = []
    for part in unique[:12]:
        pools.append((part, list(_windows(part.text, focus_terms))))
    payload = {
        "selection": "literal_windows",
        "offset_basis": "各次工具返回的单篇正文字符位置，非PDF页码；片段之间不连续",
        "documents": records,
        "source_document_count": len(unique),
    }
    for rank in range(8):
        for part, windows in pools:
            if rank >= len(windows):
                continue
            record = next(
                (
                    entry
                    for entry in records
                    if entry["url"] == part.source_url
                    and entry["body_length"] == len(part.text)
                    and entry["body_index"] == unique.index(part)
                ),
                None,
            )
            new_record = record is None
            if new_record:
                record = {
                    "url": part.source_url,
                    "body_index": unique.index(part),
                    "body_length": len(part.text),
                    "excerpts": [],
                    "truncated": True,
                }
                records.append(record)
            record["excerpts"].append(windows[rank])
            encoded = json.dumps(payload, ensure_ascii=False)
            if len(encoded) > budget:
                record["excerpts"].pop()
                if new_record:
                    records.remove(record)
    if not records:
        return None
    for record in records:
        record["excerpts"].sort(key=lambda value: value["start"])
        record["truncated"] = (
            sum(window["end"] - window["start"] for window in record["excerpts"]) < record["body_length"]
        )
    return json.dumps(payload, ensure_ascii=False)


def render_industry_evidence_section(
    item: AgentEvidence, *, index: int, item_budget: int, focus_terms: tuple[str, ...] = ()
) -> str:
    terms = tuple(dict.fromkeys(term.strip() for term in focus_terms if 2 <= len(term.strip()) <= 80))[:48]
    content = None
    if item.tool_name in {"web_fetch", "fetch_urls", "read_pdf"}:
        content = _body_payload(item, item_budget, terms)
    if content is None:
        content = serialize_context_result(item.content, item_budget)
    eid = agent_evidence_id(item)
    payload = json.dumps(
        {"evidence_id": eid, "tool_name": item.tool_name, "arguments": item.arguments[:1000], "content": content},
        ensure_ascii=False,
    )
    # Evidence may contain literal XML-like delimiters: keep it inside the JSON string.
    payload = payload.replace("<", "\\u003c").replace(">", "\\u003e")
    return f'<tool_evidence id="{eid}" index="{index}" name="{item.tool_name}">{payload}</tool_evidence>'


def report_focus_terms(result) -> tuple[str, ...]:
    terms = [result.name]
    for tier in (result.upstream, result.midstream, result.downstream):
        terms.extend(node.name or node.company or "" for node in tier[:6])
    for edge in result.relationships[:12]:
        terms.extend((edge.source_node, edge.target_node, edge.driver, edge.target_metric))
        terms.extend(edge.tracking_metrics[:3])
    return tuple(dict.fromkeys(terms))[:48]
