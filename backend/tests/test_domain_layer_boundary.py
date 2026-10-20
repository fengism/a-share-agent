"""Domain layer purity: `app.domain` must not depend on any other `app.*` layer.

The agentic core is allowed to depend on `app.domain` only. That promise is worth
nothing if the domain layer itself reaches back into `app.core` (it did:
`market_today()` lived in `app.core.market`, so the domain pulled in pandas and
the whole host core).
"""

from __future__ import annotations

import ast
from pathlib import Path

APP_DIR = Path(__file__).resolve().parents[1] / "app"
DOMAIN_DIR = APP_DIR / "domain"

# Third-party modules the domain layer is allowed to declare as its own deps.
ALLOWED_THIRD_PARTY = frozenset({"pydantic", "httpx", "requests", "typing_extensions"})


def _domain_files() -> list[Path]:
    return [
        path
        for path in sorted(DOMAIN_DIR.rglob("*.py"))
        if "__pycache__" not in path.parts
    ]


def _imports(path: Path) -> list[tuple[str, int]]:
    imports: list[tuple[str, int]] = []
    for node in ast.walk(ast.parse(path.read_text(encoding="utf-8"))):
        if isinstance(node, ast.ImportFrom) and node.module and node.level == 0:
            imports.append((node.module, node.lineno))
        elif isinstance(node, ast.Import):
            imports.extend((alias.name, node.lineno) for alias in node.names)
    return imports


def test_domain_never_imports_other_app_layers():
    violations: list[str] = []
    for path in _domain_files():
        relative = path.relative_to(APP_DIR).as_posix()
        for module, line in _imports(path):
            if not module.startswith("app."):
                continue
            if module == "app.domain" or module.startswith("app.domain."):
                continue
            violations.append(f"{relative}:{line} domain 不得依赖 {module}")

    assert not violations, "\n".join(violations)


def test_domain_third_party_surface_is_explicit():
    """新增三方依赖必须同时更新本测试和打包依赖声明，不能悄悄扩散。"""
    unexpected: set[str] = set()
    import sys

    for path in _domain_files():
        for module, _ in _imports(path):
            top = module.split(".")[0]
            if top == "app" or top in sys.stdlib_module_names:
                continue
            if top not in ALLOWED_THIRD_PARTY:
                unexpected.add(f"{top} ({path.name})")

    assert not unexpected, (
        "domain 层新增了三方依赖，需要确认抽取成独立包时能声明它："
        f"{sorted(unexpected)}"
    )


def test_market_time_definitions_have_a_single_source_of_truth():
    from app.agentic.runtime import timezones as agentic_timezones
    from app.core import timezones as core_timezones
    from app.domain import timezones as domain_timezones

    assert core_timezones.SHANGHAI_TIMEZONE is domain_timezones.SHANGHAI_TIMEZONE
    assert agentic_timezones.SHANGHAI_TIMEZONE is domain_timezones.SHANGHAI_TIMEZONE
    assert (
        core_timezones.SHANGHAI_TIMEZONE_NAME
        == agentic_timezones.SHANGHAI_TIMEZONE_NAME
        == domain_timezones.SHANGHAI_TIMEZONE_NAME
    )

    from app.core.market import market_today as core_market_today

    assert core_market_today is domain_timezones.market_today
