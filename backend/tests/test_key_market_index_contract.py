"""前端核心指数名单与后端 ``INDEX_FALLBACKS`` 的跨端契约。

``frontend/src/utils/keyMarketIndices.ts`` 里的指数名单与后端
``app/constants/market.py::INDEX_FALLBACKS`` 是同一批指数：

- 后端用它归一 ``/market/indices`` 的返回（``normalize_indices`` 会按其顺序过滤并排序）；
- 前端用它做指数页的可切换集合与顶栏行情条的挑选。

两侧漂移时不会报错，只会表现为「指数页少了某个指数」或「顶栏挑不中」，很难发现。
本测试把两侧名单与顺序绑在一起。
"""

from __future__ import annotations

import re
from pathlib import Path

import pytest

from app.constants.market import INDEX_FALLBACKS

KEY_INDICES_TS = (
    Path(__file__).resolve().parents[2] / "frontend" / "src" / "utils" / "keyMarketIndices.ts"
)

#: 匹配 ``KEY_MARKET_INDICES`` 数组里每个条目的裸代码与中文名
_ENTRY_PATTERN = re.compile(r'\{\s*code:\s*"([^"]+)"\s*,\s*name:\s*"([^"]+)"')


def _frontend_indices() -> list[tuple[str, str]]:
    assert KEY_INDICES_TS.is_file(), f"未找到前端指数名单，契约测试失效: {KEY_INDICES_TS}"
    return _ENTRY_PATTERN.findall(KEY_INDICES_TS.read_text(encoding="utf-8"))


def test_frontend_parser_is_not_silently_empty() -> None:
    """自测：解析逻辑失效时必须失败，而不是在空列表上让下面的断言通过。"""
    parsed = _frontend_indices()
    assert parsed, "未能从 keyMarketIndices.ts 解析出任何指数条目，请同步本测试的解析逻辑"
    assert len(parsed) == len(INDEX_FALLBACKS), (
        f"前端解析到 {len(parsed)} 个指数，后端有 {len(INDEX_FALLBACKS)} 个"
    )


def test_frontend_index_codes_match_backend_fallbacks_in_order() -> None:
    frontend_codes = [code for code, _name in _frontend_indices()]
    backend_codes = [code for code, _name, _secid in INDEX_FALLBACKS]
    assert frontend_codes == backend_codes, (
        "前端核心指数名单与后端 INDEX_FALLBACKS 不一致。\n"
        f"  前端: {frontend_codes}\n  后端: {backend_codes}"
    )


def test_frontend_index_names_match_backend_fallbacks() -> None:
    frontend_names = dict(_frontend_indices())
    mismatched = {
        code: (frontend_names[code], name)
        for code, name, _secid in INDEX_FALLBACKS
        if code in frontend_names and frontend_names[code] != name
    }
    assert mismatched == {}, f"前后端指数简称不一致（code: 前端, 后端）: {mismatched}"


def test_backend_fallbacks_have_no_duplicate_codes() -> None:
    codes = [code for code, _name, _secid in INDEX_FALLBACKS]
    assert len(codes) == len(set(codes)), f"INDEX_FALLBACKS 存在重复代码: {codes}"


@pytest.mark.parametrize("index_code", ["000001", "399006", "000300"])
def test_well_known_index_codes_are_covered(index_code: str) -> None:
    """抽查几个被多处引用的常用指数确实在名单里。"""
    assert index_code in [code for code, _name, _secid in INDEX_FALLBACKS]
