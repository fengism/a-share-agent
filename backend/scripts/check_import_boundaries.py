#!/usr/bin/env python3
"""后端模块边界门禁。

规则集刻意保持精简，只覆盖「会被静默侵蚀、且当前基本干净」的结构约束：

R1 分层：``app/domain`` 与 ``app/core`` 是内层，不得依赖 ``app/infrastructure`` /
   ``app/modules``；``app/infrastructure`` 同样不得依赖 ``app/modules``。
R2 私有名：跨模块引用不得使用下划线私有名（``_foo``），同模块内部引用不受限制。
R3 向上依赖：``app/core`` / ``app/domain`` / ``app/infrastructure`` / ``app/modules/**``
   不得反向依赖 ``app/api`` / ``app/runtime`` / ``app/main``。

说明：本仓库并没有把 ``app/modules/X`` 当作硬黑盒——API 路由直接引用各模块的
``models`` / ``schemas`` 是既定约定，因此**不**强制「只能 import public」。
``app/main.py``（组合根）与 ``app/scripts``（工具脚本）是 R3 的合法例外来源。

运行方式::

    uv run --frozen python -m scripts.check_import_boundaries

退出码 0 表示通过，1 表示存在越界（逐条打印 ``文件:行 [规则] 说明``）。
"""

from __future__ import annotations

import ast
import sys
from collections import defaultdict
from dataclasses import dataclass
from pathlib import Path

APP_DIR = Path(__file__).resolve().parent.parent / "app"
REPO_BACKEND_DIR = APP_DIR.parent

#: R1：{源目录：禁止依赖的 app 子包}
#:
#: ``app/core`` 与 ``app/domain`` 同属内层，允许互相引用（``request_context`` 需要
#: ``domain.identity.UserRecord``，``domain.industry_chain`` 需要 ``core.market``）。
#: 真正值得守住的是内层不得伸手到 ``infrastructure`` / ``modules``。
LAYER_FORBIDDEN: dict[str, frozenset[str]] = {
    "core": frozenset({"infrastructure", "modules", "agentic", "agentic_integration"}),
    "domain": frozenset({"infrastructure", "modules", "agentic", "agentic_integration"}),
    "infrastructure": frozenset({"modules", "agentic", "agentic_integration"}),
    "financial_data": frozenset({"modules", "agentic", "agentic_integration"}),
}

#: R3：这些 app 子包属于「上层」，内层与业务模块不得反向依赖。
UPWARD_FORBIDDEN: frozenset[str] = frozenset({"api", "runtime", "main"})

#: R3 的合法来源（组合根与工具脚本）。
UPWARD_EXEMPT_SOURCES: frozenset[str] = frozenset({"main", "scripts"})

#: ``app/modules`` 下的顶层共享内核：与 financial_data 互相依赖，按共享层处理。
SHARED_KERNEL_MODULES: frozenset[str] = frozenset(
    {
        "code_normalization",
        "import_limits",
        "master_data_revision",
    }
)

#: 已登记的既有例外，键为 ``(相对 app 的源文件路径, 目标标识)``。每条都必须写明原因，
#: 并应在条件允许时消除；新增例外需在评审中说明必要性。
KNOWN_EXCEPTIONS: dict[tuple[str, str], str] = {
    # init_db() 需要提前建好独立日行情库结构，否则首个在线备份会生成空结构副本。
    ("infrastructure/persistence/__init__.py", "modules.market_daily"): "init_db 需提前建好 market_daily 结构",
    # 图表渲染工作线程按业务类型分发，属已知依赖倒置；后续应改为模块注册制。
    ("infrastructure/chart_worker.py", "modules.analysis"): "图表渲染按业务分发，待改注册制",
    ("infrastructure/chart_worker.py", "modules.daily_review"): "图表渲染按业务分发，待改注册制",
    ("infrastructure/chart_worker.py", "modules.industry_chain"): "图表渲染按业务分发，待改注册制",
    # 版本解析与 cookie 写入目前住在 runtime / api，两侧互为依赖，宜下沉到共享层。
    ("api/version.py", "runtime"): "版本解析逻辑当前位于 runtime.app_version",
    ("runtime/middleware.py", "api"): "认证 cookie 名与写入器当前位于 api.auth.cookies",
    # ── 数据层读取本地落库数据的历史债务（基线，冻结存量、只减不增）──
    # financial_data 需要读取 market_daily / stock_profile / stock_concept /
    # industry_classification 落库的本地快照。产品当前不做端口化/仓储下沉，
    # 只冻结存量、禁止新增依赖；确实要动数据源架构时再单独评估。
    ("financial_data/hk/service.py", "modules.market_daily"): "港股日线读取本地 market_daily 仓储",
    ("financial_data/market/quotes/breadth.py", "modules.industry_classification"): "市场宽度读取本地行业映射",
    ("financial_data/market/quotes/concept_linkage.py", "modules.market_daily"): "概念指数读取本地日线仓储",
    ("financial_data/market/quotes/index_kline.py", "modules.market_daily"): "指数日线读取本地日线仓储",
    ("financial_data/stock/classification/service.py", "modules.industry_classification"): "个股分类读取本地行业映射",
    ("financial_data/stock/profile/basic_info.py", "modules.stock_concept"): "基础信息读取本地概念快照",
    ("financial_data/stock/profile/basic_info.py", "modules.industry_classification"): "基础信息读取本地行业映射",
    ("financial_data/stock/profile/basic_info.py", "modules.stock_profile"): "基础信息读取本地个股资料快照",
    ("financial_data/stock/profile/business_intro.py", "modules.stock_profile"): "主营介绍读取本地个股资料快照",
    ("financial_data/stock/quotes/kline.py", "modules.market_daily"): "个股日线读取本地日线仓储",
}


@dataclass(frozen=True, slots=True)
class Violation:
    path: str
    line: int
    rule: str
    detail: str

    def render(self) -> str:
        return f"{self.path}:{self.line} [{self.rule}] {self.detail}"


def _relative(path: Path, app_dir: Path) -> str:
    return str(path.relative_to(app_dir))


def _layer_of(path: Path, app_dir: Path) -> str:
    parts = path.relative_to(app_dir).with_suffix("").parts
    if parts[0] == "modules" and len(parts) > 1:
        return f"modules.{parts[1]}"
    return parts[0]


def _iter_app_imports(tree: ast.AST) -> list[tuple[str, list[str], int]]:
    """产出 ``(目标模块, 导入名列表, 行号)``，只关注指向 ``app.*`` 的绝对导入。"""
    found: list[tuple[str, list[str], int]] = []
    for node in ast.walk(tree):
        if isinstance(node, ast.ImportFrom):
            module = node.module or ""
            if node.level == 0 and (module == "app" or module.startswith("app.")):
                found.append((module, [alias.name for alias in node.names], node.lineno))
        elif isinstance(node, ast.Import):
            for alias in node.names:
                if alias.name == "app" or alias.name.startswith("app."):
                    found.append((alias.name, [], node.lineno))
    return found


@dataclass(frozen=True, slots=True)
class _ScanContext:
    app_dir: Path
    violations: list[Violation]


def _exempt(path: Path, target: str, app_dir: Path) -> bool:
    return (_relative(path, app_dir), target) in KNOWN_EXCEPTIONS


def _layer_target(parts: list[str]) -> str:
    """把 import 目标压成用于豁免匹配的标识（``modules.X`` 保留到二级）。"""
    if parts[1] == "modules" and len(parts) > 2:
        return f"modules.{parts[2]}"
    return parts[1]


def _check_layer(ctx: _ScanContext, path: Path, module: str, line: int) -> None:
    parts = module.split(".")
    if len(parts) < 3 or parts[0] != "app":
        return
    source = _layer_of(path, ctx.app_dir)
    forbidden = LAYER_FORBIDDEN.get(source)
    if not forbidden or parts[1] not in forbidden:
        return
    if parts[1] == "modules" and len(parts) > 2 and parts[2] in SHARED_KERNEL_MODULES:
        return
    if _exempt(path, _layer_target(parts), ctx.app_dir):
        return
    ctx.violations.append(
        Violation(
            _relative(path, ctx.app_dir),
            line,
            "layering",
            f"{source} 层不得依赖 app.{parts[1]}（{module}）",
        )
    )


def _check_upward(ctx: _ScanContext, path: Path, module: str, line: int) -> None:
    parts = module.split(".")
    if len(parts) < 2 or parts[0] != "app":
        return
    source = _layer_of(path, ctx.app_dir)
    if source in UPWARD_EXEMPT_SOURCES or parts[1] in UPWARD_EXEMPT_SOURCES:
        return
    if parts[1] not in UPWARD_FORBIDDEN or parts[1] == source:
        return
    if _exempt(path, parts[1], ctx.app_dir):
        return
    ctx.violations.append(
        Violation(
            _relative(path, ctx.app_dir),
            line,
            "upward",
            f"{source} 不得反向依赖上层 app.{parts[1]}（{module}）",
        )
    )


def _check_private_name(
    ctx: _ScanContext,
    path: Path,
    module: str,
    names: list[str],
    line: int,
) -> None:
    parts = module.split(".")
    if len(parts) < 3 or parts[:2] != ["app", "modules"]:
        return
    target_module = parts[2]
    if target_module in SHARED_KERNEL_MODULES:
        return
    if _layer_of(path, ctx.app_dir) == f"modules.{target_module}":
        return  # 同模块内部私有引用合法
    for name in names:
        if name.startswith("_"):
            ctx.violations.append(
                Violation(
                    _relative(path, ctx.app_dir),
                    line,
                    "private-name",
                    f"跨模块引用了私有名 {module}.{name}",
                )
            )


def collect_violations(app_dir: Path = APP_DIR) -> list[Violation]:
    ctx = _ScanContext(app_dir=app_dir, violations=[])
    for path in sorted(app_dir.rglob("*.py")):
        if "__pycache__" in path.parts:
            continue
        try:
            tree = ast.parse(path.read_text(encoding="utf-8"))
        except SyntaxError as error:  # pragma: no cover - 语法错误会被 ruff/pytest 更早拦住
            ctx.violations.append(
                Violation(_relative(path, app_dir), error.lineno or 0, "syntax", str(error))
            )
            continue
        for module, names, line in _iter_app_imports(tree):
            _check_layer(ctx, path, module, line)
            _check_upward(ctx, path, module, line)
            _check_private_name(ctx, path, module, names, line)
    return ctx.violations


def main() -> int:
    violations = collect_violations()
    if not violations:
        print("后端模块边界检查通过")
        return 0

    grouped: dict[str, list[Violation]] = defaultdict(list)
    for violation in violations:
        grouped[violation.rule].append(violation)

    print(f"检测到 {len(violations)} 处模块边界越界：\n")
    for rule, items in sorted(grouped.items()):
        print(f"── {rule}（{len(items)}）")
        for item in items:
            print(f"   {item.render()}")
        print()
    print(
        "确需保留时，请把 (源文件, 目标标识) 加进 "
        "scripts/check_import_boundaries.py 的 KNOWN_EXCEPTIONS 并写明原因。"
    )
    return 1


if __name__ == "__main__":
    sys.exit(main())
