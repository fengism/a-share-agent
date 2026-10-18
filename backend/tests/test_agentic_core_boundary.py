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
