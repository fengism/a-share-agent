"""后端模块边界门禁：既验证当前代码库合规，也验证检查器本身不会漏报。

第二部分的「自测」很关键：没有它的话，检查器一旦写错（例如规则恒不命中），
门禁会永远绿灯而无人察觉。
"""

from __future__ import annotations

from pathlib import Path

import pytest

from scripts.check_import_boundaries import (
    APP_DIR,
    LAYER_FORBIDDEN,
    collect_violations,
)


def test_repository_has_no_import_boundary_violations() -> None:
    violations = collect_violations()
    assert violations == [], "模块边界越界:\n" + "\n".join(v.render() for v in violations)


def _write(app_dir: Path, relative: str, source: str) -> None:
    target = app_dir / relative
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text(source, encoding="utf-8")


@pytest.fixture
def fake_app(tmp_path: Path) -> Path:
    app_dir = tmp_path / "app"
    (app_dir / "domain").mkdir(parents=True)
    (app_dir / "core").mkdir(parents=True)
    (app_dir / "infrastructure").mkdir(parents=True)
    (app_dir / "modules" / "alpha").mkdir(parents=True)
    (app_dir / "modules" / "beta").mkdir(parents=True)
    return app_dir


def test_detects_core_reaching_into_modules(fake_app: Path) -> None:
    _write(fake_app, "core/helper.py", "from app.modules.alpha.public import thing\n")

    violations = collect_violations(fake_app)

    assert [v.rule for v in violations] == ["layering"]
    assert "app.modules" in violations[0].detail


def test_detects_infrastructure_reaching_into_modules(fake_app: Path) -> None:
    _write(fake_app, "infrastructure/worker.py", "import app.modules.beta.repository\n")

    violations = collect_violations(fake_app)

    assert [v.rule for v in violations] == ["layering"]


def test_allows_domain_and_core_to_reference_each_other(fake_app: Path) -> None:
    _write(fake_app, "domain/model.py", "from app.core.market import market_today\n")
    _write(fake_app, "core/context.py", "from app.domain.model import Thing\n")

    assert collect_violations(fake_app) == []


def test_allows_cross_module_public_and_models_imports(fake_app: Path) -> None:
    _write(fake_app, "modules/alpha/service.py", "from app.modules.beta.public import run\n")
    _write(fake_app, "modules/alpha/api_models.py", "from app.modules.beta.models import Dto\n")

    assert collect_violations(fake_app) == []


def test_allows_same_module_private_import(fake_app: Path) -> None:
    _write(fake_app, "modules/alpha/service.py", "from app.modules.alpha.helpers import _inner\n")

    assert collect_violations(fake_app) == []


def test_detects_cross_module_private_name(fake_app: Path) -> None:
    _write(fake_app, "modules/alpha/service.py", "from app.modules.beta.helpers import _hidden\n")

    violations = collect_violations(fake_app)

    assert [v.rule for v in violations] == ["private-name"]
    assert "_hidden" in violations[0].detail


def test_detects_module_depending_on_api_layer(fake_app: Path) -> None:
    _write(fake_app, "modules/alpha/service.py", "from app.api.errors import ApiError\n")

    violations = collect_violations(fake_app)

    assert [v.rule for v in violations] == ["upward"]


def test_main_and_scripts_may_depend_on_upper_layers(fake_app: Path) -> None:
    _write(fake_app, "main.py", "from app.runtime import app_setup\nfrom app.api import setup\n")
    _write(fake_app, "scripts/tool.py", "from app.main import create_app\n")

    assert collect_violations(fake_app) == []


def test_checker_reports_syntax_errors_instead_of_crashing(fake_app: Path) -> None:
    _write(fake_app, "core/broken.py", "def oops(:\n")

    violations = collect_violations(fake_app)

    assert [v.rule for v in violations] == ["syntax"]


def test_known_exceptions_are_keyed_by_existing_paths() -> None:
    """例外表里的路径必须真实存在，避免代码搬迁后留下无效豁免。"""
    from scripts.check_import_boundaries import KNOWN_EXCEPTIONS

    for relative, _target in KNOWN_EXCEPTIONS:
        assert (APP_DIR / relative).is_file(), f"例外表引用了不存在的文件: {relative}"


def test_layer_rules_only_name_real_top_level_packages() -> None:
    for source, forbidden in LAYER_FORBIDDEN.items():
        assert (APP_DIR / source).is_dir(), f"规则引用了不存在的层: {source}"
        for target in forbidden:
            assert (APP_DIR / target).exists(), f"规则引用了不存在的层: {target}"
