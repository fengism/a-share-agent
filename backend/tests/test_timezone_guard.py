"""时间基准门禁：业务代码不得使用"容器本地时区"的``datetime.now()``/``date.today()``。

**背景**：``docker-compose`` 用 ``TZ`` 环境变量把容器时区纠正成 Asia/Shanghai，但裸机、
k8s、CI、开发机通常没有设置。此时 ``datetime.now()`` 是 UTC 墙上时间，与用户在浏览器
里看到的北京时间相差 8 小时——「行情时间」「生成时间」「今天」都会错（每天 00:00–08:00
尤其明显，日期直接差一天）。

因此统一使用 ``app.domain.timezones``：

- ``market_now()`` → 市场时区的 naive 墙上时间（保持既有字符串格式）；
- ``market_today()`` → 市场时区的当天日期。

本测试用 AST 扫描兜住回退：只允许 ``timezones`` 自己调用带时区的写法。
"""

from __future__ import annotations

import ast
from pathlib import Path

APP_DIR = Path(__file__).resolve().parent.parent / "app"

#: 允许出现 naive 时间基准的文件（时区权威定义本身）。
ALLOWED_FILES = {"app/domain/timezones.py"}


def _iter_naive_time_calls(path: Path) -> list[tuple[int, str]]:
    tree = ast.parse(path.read_text(encoding="utf-8"))
    offenders: list[tuple[int, str]] = []
    for node in ast.walk(tree):
        if not isinstance(node, ast.Call):
            continue
        func = node.func
        if not isinstance(func, ast.Attribute):
            continue
        if any(keyword.arg for keyword in node.keywords) or node.args:
            # datetime.now(UTC) / date.today() 之外的形态不在此列
            continue
        owner = ast.unparse(func.value)
        name = f"{owner}.{func.attr}"
        if name in {"datetime.now", "date.today"}:
            offenders.append((node.lineno, name))
    return offenders


def test_no_naive_wall_clock_in_app_code() -> None:
    offenders: list[str] = []
    for path in sorted(APP_DIR.rglob("*.py")):
        relative = str(path.relative_to(APP_DIR.parent))
        if relative in ALLOWED_FILES:
            continue
        for lineno, name in _iter_naive_time_calls(path):
            offenders.append(f"{relative}:{lineno} {name}()")
    assert not offenders, (
        "业务代码必须使用 app.domain.timezones 的 market_now()/market_today()，"
        "或带时区的 datetime.now(SHANGHAI_TIMEZONE)：\n" + "\n".join(offenders)
    )


def test_timezone_guard_detects_a_regression(tmp_path: Path) -> None:
    """守卫本身要能报错，避免将来被改坏成永远通过。"""
    sample = tmp_path / "sample.py"
    sample.write_text(
        "from datetime import date, datetime\n\n"
        "def f():\n"
        "    return datetime.now(), date.today()\n",
        encoding="utf-8",
    )
    found = _iter_naive_time_calls(sample)
    assert [name for _, name in found] == ["datetime.now", "date.today"]


def test_aware_and_market_helpers_are_not_flagged(tmp_path: Path) -> None:
    sample = tmp_path / "ok.py"
    sample.write_text(
        "from datetime import datetime\n\n"
        "from app.domain.timezones import SHANGHAI_TIMEZONE, market_now\n\n"
        "def f():\n"
        "    return datetime.now(SHANGHAI_TIMEZONE), market_now()\n",
        encoding="utf-8",
    )
    assert _iter_naive_time_calls(sample) == []
