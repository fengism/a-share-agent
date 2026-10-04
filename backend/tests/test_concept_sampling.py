"""概念成分股抽样：必须对板块无偏，且完全确定可复现。"""

from __future__ import annotations

import sys
from collections import Counter
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from app.modules.market_daily.concept_index import MAX_CONSTITUENTS, sample_constituents  # noqa: E402


def board_of(code: str) -> str:
    if code.startswith("688"):
        return "科创板"
    if code[:3] in {"300", "301"}:
        return "创业板"
    if code.startswith("6"):
        return "沪主板"
    if code[:1] in {"8", "9", "4"}:
        return "北交所"
    return "深主板"


def build_realistic_codes(count: int) -> list[str]:
    """按真实 A 股代码分布造一份升序列表（代码前缀天然按板块分段）。"""
    pools = {
        "深主板": [f"{n:06d}" for n in range(2, 3000)],
        "创业板": [f"30{n:04d}" for n in range(1, 1200)],
        "北交所": [f"8{n:05d}" for n in range(30000, 30200)],
        "沪主板": [f"60{n:04d}" for n in range(1000, 2400)],
        "科创板": [f"688{n:03d}" for n in range(100, 800)],
    }
    codes: list[str] = []
    per_board = max(1, count // len(pools))
    for pool in pools.values():
        codes.extend(pool[:per_board])
    codes.sort()
    return codes[:count]


def test_small_concepts_are_returned_untouched() -> None:
    codes = build_realistic_codes(500)
    assert sample_constituents(codes) == codes


def test_oversized_concept_is_capped_exactly() -> None:
    codes = build_realistic_codes(MAX_CONSTITUENTS + 900)
    sampled = sample_constituents(codes)
    assert len(sampled) == MAX_CONSTITUENTS
    assert len(set(sampled)) == MAX_CONSTITUENTS


def test_sampling_is_deterministic() -> None:
    codes = build_realistic_codes(MAX_CONSTITUENTS + 500)
    assert sample_constituents(codes) == sample_constituents(codes)


def test_sampling_preserves_every_board() -> None:
    """回归：按代码排序取前 N 会把高前缀板块（科创板 688、北交所 8xxxxx）整段丢掉。

    实测"机器人概念"从 1225 只截到 800 只后，科创板 170 只、北交所 59 只
    全部消失，而这正是机器人/人工智能类概念的核心成分。
    """
    codes = build_realistic_codes(MAX_CONSTITUENTS + 1500)
    full = Counter(board_of(code) for code in codes)
    sampled = Counter(board_of(code) for code in sample_constituents(codes))

    assert set(sampled) == set(full), "有板块在抽样后整体消失"
    for board, total in full.items():
        keep_ratio = sampled[board] / total
        assert keep_ratio > 0.25, f"{board} 保留率过低：{keep_ratio:.2%}"
        assert keep_ratio < 0.75, f"{board} 保留率过高：{keep_ratio:.2%}"


def test_empty_input() -> None:
    assert sample_constituents([]) == []
