"""用户可见错误消息不得拼接底层异常。

背景：``ApplicationError`` 的 ``message`` 会原样返回给客户端
（``application_error_handler`` 仅追加错误编号，不做脱敏）。若把 ``str(exc)``
拼进去，上游请求 URL、接口参数、内部类名甚至 SQL 都会顺着 5xx 响应泄漏出去。

**只针对宽泛捕获**：``except Exception as exc`` 兜住了意料之外的失败，其文本可能
是任意内部细节，这类异常绝不能进 5xx 的 message。反过来，``except
LLMConfigurationError as error`` 这种按类型精确捕获的领域异常，message 本就是写给
用户看的提示，转为 4xx 是正确设计，不在本规则约束范围内。
"""

from __future__ import annotations

import ast
from pathlib import Path

APP_DIR = Path(__file__).resolve().parents[1] / "app"

#: message 会直达客户端的异常类型（见 app/api/errors.py 的处理器注册）。
_CLIENT_VISIBLE_ERRORS = frozenset({
    "ApiError",
    "ApplicationError",
    "InvalidRequestError",
    "ResourceNotFoundError",
    "ResourceConflictError",
    "UpstreamUnavailableError",
    "UpstreamEmptyResponseError",
    "UpstreamRateLimitedError",
})
#: 允许出现在消息里的「异常」名字：这些是调用方显式构造的、本身就面向用户的文本。
_ALLOWED_EXCEPTION_NAMES = frozenset({"error_message", "reason", "public_message"})


#: 宽泛捕获：兜住「意料之外」的失败，其文本不可信。
_BROAD_EXCEPTIONS = frozenset({"Exception", "BaseException"})


def _is_client_visible_call(node: ast.Raise) -> bool:
    exc = node.exc
    if not isinstance(exc, ast.Call):
        return False
    func = exc.func
    name = func.id if isinstance(func, ast.Name) else getattr(func, "attr", None)
    return name in _CLIENT_VISIBLE_ERRORS


def _is_broad_handler(handler: ast.ExceptHandler) -> bool:
    if handler.type is None:
        return True
    types = handler.type.elts if isinstance(handler.type, ast.Tuple) else [handler.type]
    return any(isinstance(t, ast.Name) and t.id in _BROAD_EXCEPTIONS for t in types)


def _raises_embedding(node: ast.AST, names: set[str]) -> list[str]:
    """在当前 AST 子树里找「把 ``names`` 中的异常文本塞进用户可见消息」的 raise。"""
    found: list[str] = []
    for sub in ast.walk(node):
        if not isinstance(sub, ast.Raise) or not _is_client_visible_call(sub):
            continue
        assert isinstance(sub.exc, ast.Call)
        for arg in [*sub.exc.args, *(kw.value for kw in sub.exc.keywords)]:
            for inner in ast.walk(arg):
                # f-string 的 {exc} / {str(exc)} / {exc!r} 都会命中这几种形态
                if isinstance(inner, ast.Name) and inner.id in names:
                    found.append(f"line {sub.lineno} 引用了 {inner.id}")
                if (
                    isinstance(inner, ast.Call)
                    and isinstance(inner.func, ast.Name)
                    and inner.func.id == "str"
                    and inner.args
                    and isinstance(inner.args[0], ast.Name)
                    and inner.args[0].id in names
                ):
                    found.append(f"line {sub.lineno} 引用了 str({inner.args[0].id})")
    return found


def _offenders(path: Path) -> list[str]:
    tree = ast.parse(path.read_text(encoding="utf-8"))
    found: list[str] = []
    # 按 handler 作用域检查：只看 ``except Exception as exc`` 自己的 body。
    # 全文件收集名字会误报——同文件不同 try 里的同名变量互不相关。
    for handler in ast.walk(tree):
        if not isinstance(handler, ast.ExceptHandler):
            continue
        if not _is_broad_handler(handler) or not handler.name:
            continue
        if handler.name in _ALLOWED_EXCEPTION_NAMES:
            continue
        for detail in _raises_embedding(handler_body(handler), {handler.name}):
            found.append(f"{path.relative_to(APP_DIR.parent)}:{handler.lineno} {detail}")
    return found


def handler_body(handler: ast.ExceptHandler) -> ast.AST:
    return ast.Module(body=handler.body, type_ignores=[])


def test_client_visible_error_messages_do_not_embed_underlying_exception() -> None:
    offenders: list[str] = []
    for path in sorted(APP_DIR.rglob("*.py")):
        if "__pycache__" in path.parts:
            continue
        try:
            offenders.extend(_offenders(path))
        except SyntaxError:
            continue
    assert offenders == [], (
        "以下用户可见错误消息拼接了底层异常（会经 5xx 响应泄漏内部细节），"
        "请改为固定文案并保留 `from exc`: " + ", ".join(offenders)
    )
