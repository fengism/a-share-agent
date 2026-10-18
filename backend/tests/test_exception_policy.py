"""异常处理策略守卫。

规则（`app/` 内）：

1. 禁止裸 ``except:``；
2. ``except Exception`` 必须可诊断：处理块内要么记日志，要么重新抛出；只有
   ``pass`` / ``continue`` / ``return`` / ``break`` 的静默吞异常一律不允许。

新增此类代码必须补日志或 re-raise，而不是把失败悄悄降级。
"""

from __future__ import annotations

import ast
from pathlib import Path

APP_DIR = Path(__file__).resolve().parents[1] / "app"
_LOGGING_NAMES = frozenset({"debug", "info", "warning", "error", "exception", "critical", "log"})


def _iter_handlers(tree: ast.AST):
    for node in ast.walk(tree):
        if isinstance(node, ast.ExceptHandler):
            yield node


def _handler_is_diagnostic(handler: ast.ExceptHandler) -> bool:
    body = handler.body
    module = ast.Module(body=body, type_ignores=[])
    for node in ast.walk(module):
        if isinstance(node, ast.Raise):
            return True
        if isinstance(node, ast.Call):
            func = node.func
            name = func.attr if isinstance(func, ast.Attribute) else (func.id if isinstance(func, ast.Name) else "")
            if name in _LOGGING_NAMES:
                return True
    return not all(isinstance(stmt, (ast.Pass, ast.Continue, ast.Return, ast.Break)) for stmt in body)


def test_no_bare_except_in_app() -> None:
    offenders: list[str] = []
    for path in sorted(APP_DIR.rglob("*.py")):
        if "__pycache__" in path.parts:
            continue
        try:
            tree = ast.parse(path.read_text(encoding="utf-8"))
        except SyntaxError as error:
            raise AssertionError(f"{path} 语法错误: {error}") from error
        for handler in _iter_handlers(tree):
            if handler.type is None:
                offenders.append(f"{path.relative_to(APP_DIR.parent)}:{handler.lineno}")
    assert offenders == [], f"发现裸 except:，请改为具体异常并处理: {offenders}"


def test_broad_except_is_logged_or_reraised() -> None:
    offenders: list[str] = []
    for path in sorted(APP_DIR.rglob("*.py")):
        if "__pycache__" in path.parts:
            continue
        try:
            tree = ast.parse(path.read_text(encoding="utf-8"))
        except SyntaxError:
            continue
        for handler in _iter_handlers(tree):
            if handler.type is None or ast.unparse(handler.type) != "Exception":
                continue
            if not _handler_is_diagnostic(handler):
                offenders.append(f"{path.relative_to(APP_DIR.parent)}:{handler.lineno}")
    assert offenders == [], (
        "以下 except Exception 静默吞掉异常，必须补 logger 或 re-raise: " + ", ".join(offenders)
    )
