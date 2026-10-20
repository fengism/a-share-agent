"""Keep the agentic core extractable: no host or integration imports.

The host-facing surfaces live in ``app.agentic_integration`` and may import the
application. The core runtime must only depend on itself and ``app.domain``.
"""

from __future__ import annotations

import ast
from pathlib import Path

APP_DIR = Path(__file__).resolve().parents[1] / "app"
AGENTIC_DIR = APP_DIR / "agentic"


class _ImportVisitor(ast.NodeVisitor):
    def __init__(self) -> None:
        self.imports: list[tuple[str, int]] = []

    def visit_ImportFrom(self, node: ast.ImportFrom) -> None:
        if node.module:
            self.imports.append((node.module, node.lineno))
        self.generic_visit(node)

    def visit_Import(self, node: ast.Import) -> None:
        for alias in node.names:
            self.imports.append((alias.name, node.lineno))
        self.generic_visit(node)


def _core_files() -> list[Path]:
    return [
        path
        for path in sorted(AGENTIC_DIR.rglob("*.py"))
        if "__pycache__" not in path.parts
    ]


def _violations() -> list[str]:
    violations: list[str] = []
    for path in _core_files():
        relative = path.relative_to(APP_DIR).as_posix()
        visitor = _ImportVisitor()
        visitor.visit(ast.parse(path.read_text(encoding="utf-8")))
        for module, line in visitor.imports:
            if not module.startswith("app."):
                continue
            if module == "app.domain" or module.startswith("app.domain."):
                continue
            if module == "app.agentic" or module.startswith("app.agentic."):
                continue
            if module == "app.agentic_integration" or module.startswith("app.agentic_integration."):
                violations.append(
                    f"{relative}:{line} 核心模块不得导入集成层 {module}"
                )
                continue
            violations.append(
                f"{relative}:{line} 核心模块不得依赖宿主模块 {module}（仅允许 app.domain）"
            )
    return violations


def test_agentic_core_only_depends_on_domain():
    violations = _violations()

    assert not violations, "\n".join(violations)


FORBIDDEN_CORE_PATHS = (
    "adapters",
    "bootstrap.py",
    "agents/catalog.py",
    "agents/prompts.py",
    "agents/profiles",
    "agents/service.py",
    "skills/catalog.py",
    "skills/packs",
    "tools/packs",
    "tools/registration.py",
)


def test_integration_lives_outside_core():
    existing = [path for path in FORBIDDEN_CORE_PATHS if (AGENTIC_DIR / path).exists()]

    assert not existing, f"集成层文件不应放在核心包内: {existing}"


# 空的 allowlist：核心曾经通过 ``app/__init__.py`` 泄漏到
# ``app.infrastructure.javascript_runtime``（MiniRacer 的 atexit 兜底 guard）。
# 该 guard 已挪到真正 import akshare 的 ``app.infrastructure.providers.*``，
# 因此这里必须是空集：任何新的宿主依赖都会让本测试直接失败。
KNOWN_HOST_LEAKS: frozenset[str] = frozenset()

_IMPORT_PROBE = r"""
import importlib
import pathlib
import sys

HOST_PREFIXES = (
    "app.api",
    "app.configuration",
    "app.constants",
    "app.core",
    "app.financial_data",
    "app.infrastructure",
    "app.modules",
    "app.runtime",
    "app.agentic_integration",
)

recorded = set()
namespace = {"__name__": "_probe"}


class _Recorder:
    # Record (not block) every app.* module the core actually imports.

    def find_spec(self, name, path=None, target=None):
        if name == "app" or name.startswith("app."):
            recorded.add(name)
        return None


sys.meta_path.insert(0, _Recorder())

root = pathlib.Path("app/agentic")
modules = []
for path in sorted(root.rglob("*.py")):
    if "__pycache__" in path.parts:
        continue
    parts = list(path.with_suffix("").parts)
    if parts[-1] == "__init__":
        parts = parts[:-1]
    modules.append(".".join(parts))

for name in modules:
    importlib.import_module(name)

# ``app/__init__`` 本身会 import 宿主模块，所以这里只报告「核心源码里没有
# 出现、却因为包初始化被拉进来」的额外宿主模块。
# 只保留最具体的模块名：``from app.infrastructure.x import y`` 会同时记下
# ``app.infrastructure`` 与 ``app.infrastructure.x``。
leaks = sorted(
    name
    for name in recorded
    if any(name == prefix or name.startswith(prefix + ".") for prefix in HOST_PREFIXES)
    and not any(other.startswith(name + ".") for other in recorded)
)
print("\n".join(leaks))
"""


def test_core_runtime_import_surface_has_no_new_host_leaks():
    """静态检查看不到「由 app/__init__ 间接拉进来」的宿主模块，这里补上运行时证据。"""
    import subprocess
    import sys

    completed = subprocess.run(
        [sys.executable, "-c", _IMPORT_PROBE],
        cwd=AGENTIC_DIR.parents[1],
        capture_output=True,
        text=True,
        timeout=180,
    )

    assert completed.returncode == 0, completed.stderr
    leaks = {line.strip() for line in completed.stdout.splitlines() if line.strip()}
    unexpected = sorted(leaks - KNOWN_HOST_LEAKS)
    assert not unexpected, (
        "核心模块在运行时引入了新的宿主依赖（抽取成独立包后会直接 ImportError）："
        f"{unexpected}"
    )


def test_core_transitive_domain_dependencies_stay_inside_the_contract():
    """`app.domain` 里已有模块 import 了 `app.core`（industry_chain），
    所以只查直接 import 不足以证明核心可抽取；这里查传递闭包。"""
    allowed_prefixes = ("app.agentic", "app.domain")

    seen: set[str] = set()
    queue: set[str] = {module for path in _core_files() for module in _app_imports(path)}
    outside: list[str] = []
    while queue:
        module = queue.pop()
        if module in seen:
            continue
        seen.add(module)
        if not any(module == prefix or module.startswith(prefix + ".") for prefix in allowed_prefixes):
            outside.append(module)
            continue
        resolved = _resolve_app_module(module)
        if resolved is not None:
            queue |= _app_imports(resolved)

    assert not outside, f"核心的传递依赖越界: {sorted(outside)}"


def _app_imports(path: Path) -> set[str]:
    visitor = _ImportVisitor()
    visitor.visit(ast.parse(path.read_text(encoding="utf-8")))
    return {module for module, _ in visitor.imports if module == "app" or module.startswith("app.")}


def _resolve_app_module(module: str) -> Path | None:
    base = APP_DIR.joinpath(*module.split(".")[1:])
    for candidate in (base.with_suffix(".py"), base / "__init__.py"):
        if candidate.exists():
            return candidate
    return None
