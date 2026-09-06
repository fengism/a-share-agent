"""Python 计算沙盒执行服务。

隔离策略（纵深防御）：
1. AST 白名单：仅允许导入科学计算白名单模块，禁止一切 dunder 访问与
   eval/exec/getattr 等逃生舱调用——正则黑名单可被 importlib.import_module
   等手法绕过，AST 检查从语法层封死。
2. 子进程最小环境：不继承父进程环境变量（防止 LLM API key 泄露），
   工作目录为一次性临时目录，stdin 关闭，解释器隔离模式（-I）运行。
3. 资源限制：RLIMIT_AS/RLIMIT_CPU/RLIMIT_FSIZE 限制内存、CPU 与文件写入。
4. 输出上限：stdout/stderr 超 1 MB 即终止进程，防止撑爆父进程内存。

已知残余风险：pandas/numpy 本身具备文件读取能力（如 pd.read_csv），无法在
AST 层区分合法计算与恶意读取；配合工具层的仅管理员门控与最小环境兜底。
"""

from __future__ import annotations

import ast
import asyncio
import os
import re
import shutil
import sys
import tempfile
from typing import Any

_TIMEOUT_SECONDS = 5.0
_MAX_OUTPUT_BYTES = 1_000_000

# 允许导入的模块白名单（与预注入的科学计算环境保持一致）
_ALLOWED_IMPORT_MODULES = frozenset({
    "collections",
    "datetime",
    "decimal",
    "fractions",
    "functools",
    "itertools",
    "json",
    "math",
    "numpy",
    "pandas",
    "random",
    "re",
    "statistics",
    "time",
})

# 禁止直接调用的内建逃生舱（getattr 可读取 __globals__ 等内部状态）
_BANNED_BUILTIN_CALLS = frozenset({
    "__import__",
    "breakpoint",
    "compile",
    "delattr",
    "dir",
    "eval",
    "exec",
    "getattr",
    "globals",
    "input",
    "locals",
    "open",
    "setattr",
    "vars",
})

# 第一道粗筛：既有高危指令黑名单，命中即拒
_DANGEROUS_PATTERNS = (
    r"\bimport\s+os\b",
    r"\bfrom\s+os\b",
    r"\bimport\s+subprocess\b",
    r"\bfrom\s+subprocess\b",
    r"\bimport\s+sys\b",
    r"\bfrom\s+sys\b",
    r"\bimport\s+shutil\b",
    r"\bfrom\s+shutil\b",
    r"\bimport\s+socket\b",
    r"\bfrom\s+socket\b",
    r"\bimport\s+urllib\b",
    r"\bfrom\s+urllib\b",
    r"\bimport\s+requests\b",
    r"\bfrom\s+requests\b",
    r"\bimport\s+httpx\b",
    r"\bfrom\s+httpx\b",
    r"\bimport\s+aiohttp\b",
    r"\bfrom\s+aiohttp\b",
    r"\bopen\s*\(",
    r"\beval\s*\(",
    r"\bexec\s*\(",
    r"\b__import__\s*\(",
    r"\bglobals\s*\(",
    r"\blocals\s*\(",
    r"\bos\.",
    r"\bsys\.",
    r"\bsubprocess\.",
)

_PRE_INJECTED_ENV = """
import math
import datetime
import json
import re
from decimal import Decimal

try:
    import numpy as np
except ImportError:
    pass

try:
    import pandas as pd
    pd.set_option('display.max_columns', 20)
    pd.set_option('display.width', 1000)
except ImportError:
    pass
"""


class _OutputLimitExceeded(Exception):
    pass


def _check_code_safety(code: str) -> str | None:
    """静态安全检查：黑名单粗筛 + AST 白名单，返回拦截原因或 None。"""
    for pattern in _DANGEROUS_PATTERNS:
        if re.search(pattern, code, re.IGNORECASE):
            return f"安全拦截: 禁止在计算沙盒中使用潜在高危指令（匹配规则: {pattern}）"
    return _check_code_ast(code)


def _check_code_ast(code: str) -> str | None:
    try:
        tree = ast.parse(code)
    except SyntaxError as exc:
        return f"代码语法错误: {exc}"

    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            for alias in node.names:
                root = alias.name.split(".")[0]
                if root not in _ALLOWED_IMPORT_MODULES:
                    return (
                        "安全拦截: 不允许导入模块 "
                        f"{alias.name!r}（仅允许: {sorted(_ALLOWED_IMPORT_MODULES)}）"
                    )
        elif isinstance(node, ast.ImportFrom):
            root = (node.module or "").split(".")[0]
            if root not in _ALLOWED_IMPORT_MODULES:
                return f"安全拦截: 不允许从模块 {node.module!r} 导入"
        elif isinstance(node, ast.Attribute):
            if node.attr.startswith("__") and node.attr.endswith("__"):
                return f"安全拦截: 禁止访问 dunder 属性 {node.attr!r}"
        elif isinstance(node, ast.Name):
            if node.id.startswith("__") and node.id.endswith("__"):
                return f"安全拦截: 禁止引用 dunder 名称 {node.id!r}"
        elif isinstance(node, ast.Call):
            func = node.func
            if isinstance(func, ast.Name) and func.id in _BANNED_BUILTIN_CALLS:
                return f"安全拦截: 禁止调用 {func.id}()"
    return None


def _child_env() -> dict[str, str]:
    """最小子进程环境：不继承父进程变量，防止 API key 等机密泄露。"""
    allowed_keys = ("PATH", "LANG", "LC_ALL", "TMPDIR", "PYTHONIOENCODING", "PYTHONUTF8")
    return {key: os.environ[key] for key in allowed_keys if key in os.environ}


def _apply_child_resource_limits() -> None:  # pragma: no cover - 在子进程中执行
    import resource

    limits = (
        (resource.RLIMIT_AS, 512 * 1024 * 1024),
        (resource.RLIMIT_CPU, (4, 4)),
        (resource.RLIMIT_FSIZE, (1, 1)),  # 禁止写文件
        (resource.RLIMIT_NPROC, (64, 64)),
    )
    for limit, value in limits:
        try:
            resource.setrlimit(limit, value if isinstance(value, tuple) else (value, value))
        except (ValueError, OSError):
            pass


async def _read_limited(stream: asyncio.StreamReader | None, limit: int) -> bytes:
    if stream is None:
        return b""
    chunks: list[bytes] = []
    total = 0
    while True:
        chunk = await stream.read(65536)
        if not chunk:
            break
        total += len(chunk)
        if total > limit:
            raise _OutputLimitExceeded()
        chunks.append(chunk)
    return b"".join(chunks)


async def execute_python_code(code: str, timeout: float = _TIMEOUT_SECONDS) -> dict[str, Any]:
    """在隔离子进程沙盒中执行 Python 代码并捕获输出。"""
    security_error = _check_code_safety(code)
    if security_error:
        return {
            "ok": False,
            "error": security_error,
            "output": "",
        }

    full_script = f"{_PRE_INJECTED_ENV}\n{code}\n"
    workdir = tempfile.mkdtemp(prefix="py-sandbox-")
    try:
        proc = await asyncio.create_subprocess_exec(
            sys.executable,
            "-I",
            "-c",
            full_script,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE,
            stdin=asyncio.subprocess.DEVNULL,
            cwd=workdir,
            env=_child_env(),
            preexec_fn=_apply_child_resource_limits,
        )
        try:
            read_task = asyncio.gather(
                _read_limited(proc.stdout, _MAX_OUTPUT_BYTES),
                _read_limited(proc.stderr, _MAX_OUTPUT_BYTES),
            )
            stdout_bytes, stderr_bytes = await asyncio.wait_for(read_task, timeout=timeout)
        except TimeoutError:
            try:
                proc.kill()
            except ProcessLookupError:
                pass
            await proc.wait()
            return {
                "ok": False,
                "error": f"代码执行超时（超过 {timeout} 秒安全上限，已终止进程）",
                "output": "",
            }
        except _OutputLimitExceeded:
            try:
                proc.kill()
            except ProcessLookupError:
                pass
            await proc.wait()
            return {
                "ok": False,
                "error": f"输出超过 {_MAX_OUTPUT_BYTES} 字节上限，已终止进程",
                "output": "",
            }

        stdout_text = stdout_bytes.decode("utf-8", errors="replace").strip()
        stderr_text = stderr_bytes.decode("utf-8", errors="replace").strip()

        if proc.returncode != 0:
            return {
                "ok": False,
                "error": stderr_text or f"进程异常退出 (退出码 {proc.returncode})",
                "output": stdout_text,
            }

        return {
            "ok": True,
            "output": stdout_text if stdout_text else "（代码执行成功，无标准输出。提示：请使用 print(...) 打印需要查看的计算结果）",
        }
    except Exception as exc:
        return {
            "ok": False,
            "error": f"沙盒执行异常: {exc}",
            "output": "",
        }
    finally:
        shutil.rmtree(workdir, ignore_errors=True)
