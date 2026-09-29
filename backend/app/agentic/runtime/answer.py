"""Shared, conservative filtering for final answers (not evidence verification)."""

from __future__ import annotations

import re

from app.agentic.tools.calls import ToolCallMarkupStreamFilter

# Only reject explicit first-person data-gathering promises. Advice, short answers,
# evidence gaps and facts must not be rejected merely because they are brief.
_PROCESS_ONLY = re.compile(
    r"^(?:(?:现在|接下来|首先|然后|好的)[，,:：\s]*)*"
    r"(?:让我|我(?:将|会|先|需要|来|要))\s*(?:再|继续|先|进一步)?\s*"
    r"(?:获取|查询|搜索|检索|调用|查看|收集|核实|分析一下)"
    r"|^(?:(?:now|next|first)[,:\s]+)?(?:let me|i (?:will|need to|am going to))\s+"
    r"(?:first\s+|now\s+)?(?:fetch|search|look up|retrieve|call|gather|check)\b",
    re.IGNORECASE,
)
_BOUNDARY = re.compile(r"[。！？!?；;\n]|\.(?=\s)")
_OPINION = re.compile(r"```agent-opinion\s*.*?(?:```|$)", re.DOTALL)


_CLAUSE = re.compile(r"[，,:：]")
_SUBSTANTIVE_TAIL = re.compile(
    r"^(?:但|不过|然而|目前|现有|根据|截至|公告|财报|数据|公司|营收|收入|净利润|利润|现金流|"
    r"股价|估值|资金|风险|因此|所以|建议|不宜|无法|不能|尚未|已确认|已披露|已核实|已获得)"
    r"|^(?:but|however|currently|the\s+(?:reported|company|revenue|profit|data)|"
    r"according to|reported|revenue|profit|we know)\b",
    re.IGNORECASE,
)
_PROCESS_CONTINUATION = re.compile(
    r"^(?:(?:然后|再|最后|接着|随后|并|同时|继续)\s*)*(?:获取|查询|检索|搜索|查看|调用|核实)"
    r"|^(?:(?:then|next|and)\s+)*(?:fetch|search|look up|check|retrieve)\b",
    re.IGNORECASE,
)


def _clean_sentence(text: str) -> str:
    prefix = text.lstrip(" \t#*-0123456789.、")
    if not _PROCESS_ONLY.search(prefix):
        return text
    # Only the first clause is certainly narration. Do not erase factual/risk
    # clauses attached by commas, colons or a contrast conjunction.
    for match in _CLAUSE.finditer(prefix):
        tail = prefix[match.end() :].lstrip()
        if _PROCESS_ONLY.search(tail) or _PROCESS_CONTINUATION.search(tail):
            continue
        if _SUBSTANTIVE_TAIL.search(tail):
            return tail
    return ""


class AnswerTextStream:
    """Remove wire markup and process-only sentences before sending irreversible deltas.

    At most one sentence is held back; valid completed sentences remain visible if
    the provider times out or the user cancels. Markup split over chunks is handled
    by the existing wire filter.
    """

    def __init__(self) -> None:
        self._markup = ToolCallMarkupStreamFilter()
        self._pending = ""

    def _drain(self, *, final: bool = False) -> str:
        parts: list[str] = []
        while match := _BOUNDARY.search(self._pending):
            sentence = self._pending[: match.end()]
            self._pending = self._pending[match.end() :]
            parts.append(_clean_sentence(sentence))
        if final:
            parts.append(_clean_sentence(self._pending))
            self._pending = ""
        return "".join(parts)

    def feed(self, text: str) -> str:
        self._pending += self._markup.feed(text)
        return self._drain()

    def flush(self) -> str:
        self._pending += self._markup.flush()
        return self._drain(final=True)


def clean_answer(text: str) -> str:
    stream = AnswerTextStream()
    cleaned = (stream.feed(text) + stream.flush()).strip()
    # A machine-readable opinion alone is not a user-facing analysis.
    if not _OPINION.sub("", cleaned).strip():
        return ""
    return cleaned
