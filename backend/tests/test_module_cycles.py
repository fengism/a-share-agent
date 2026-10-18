"""包级依赖环守卫。

用 AST 解析 ``app`` 下的绝对导入，把 ``app.<layer>`` / ``app.modules.<name>``
压成节点后检测强连通分量（SCC）。本仓库历史包袱允许存在以下三个环：

1. ``{api, runtime}`` —— 版本解析与认证 cookie 分居两侧；
2. 数据层/基础设施/若干业务模块组成的大环（详见 BASELINE 注释）；
3. ``{core, domain}`` —— 内层互相引用（request_context ↔ domain.identity 等）。

新增环意味着新的双向耦合，必须显式修改本基线并说明理由，否则测试失败。
"""

from __future__ import annotations

import ast
from collections import defaultdict
from pathlib import Path

APP_DIR = Path(__file__).resolve().parents[1] / "app"

#: 冻结基线：每个元素是一个有序节点列表。新增/删除环都必须同步修改这里。
BASELINE: frozenset[tuple[str, ...]] = frozenset(
    {
        ("api", "runtime"),
        ("core", "domain"),
        (
            "agentic",
            "financial_data",
            "infrastructure",
            "modules.analysis",
            "modules.daily_review",
            "modules.industry_chain",
            "modules.industry_classification",
            "modules.market_daily",
            "modules.stock_concept",
            "modules.stock_profile",
            "modules.workflow",
        ),
    }
)


def _node_for(path: Path) -> str:
    parts = path.relative_to(APP_DIR).with_suffix("").parts
    if parts[0] == "modules" and len(parts) > 1:
        return f"modules.{parts[1]}"
    return parts[0]


def _imports(path: Path) -> set[str]:
    try:
        tree = ast.parse(path.read_text(encoding="utf-8"))
    except (OSError, SyntaxError):
        return set()
    modules: set[str] = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.ImportFrom) and node.level == 0 and node.module:
            if node.module == "app" or node.module.startswith("app."):
                modules.add(node.module)
        elif isinstance(node, ast.Import):
            for alias in node.names:
                if alias.name == "app" or alias.name.startswith("app."):
                    modules.add(alias.name)
    targets: set[str] = set()
    for module in modules:
        parts = module.split(".")
        if len(parts) < 2 or parts[0] != "app":
            continue
        if parts[1] == "modules" and len(parts) > 2:
            targets.add(f"modules.{parts[2]}")
        else:
            targets.add(parts[1])
    return targets


def _build_graph() -> dict[str, set[str]]:
    graph: dict[str, set[str]] = defaultdict(set)
    for path in sorted(APP_DIR.rglob("*.py")):
        if "__pycache__" in path.parts:
            continue
        source = _node_for(path)
        for target in _imports(path):
            if target != source:
                graph[source].add(target)
    return graph


def _strongly_connected_components(graph: dict[str, set[str]]) -> list[tuple[str, ...]]:
    nodes = set(graph) | {target for targets in graph.values() for target in targets}
    reverse: dict[str, set[str]] = defaultdict(set)
    for source, targets in graph.items():
        for target in targets:
            reverse[target].add(source)

    visited: set[str] = set()
    order: list[str] = []

    def visit(node: str) -> None:
        # 节点数量很小，显式栈遍历，避免递归深度问题。
        stack = [(node, iter(graph.get(node, ())))]
        visited.add(node)
        while stack:
            current, children = stack[-1]
            advanced = False
            for child in children:
                if child in nodes and child not in visited:
                    visited.add(child)
                    stack.append((child, iter(graph.get(child, ()))))
                    advanced = True
                    break
            if not advanced:
                order.append(current)
                stack.pop()

    for node in sorted(nodes):
        if node not in visited:
            visit(node)

    assigned: set[str] = set()
    components: list[tuple[str, ...]] = []

    def collect(root: str) -> None:
        stack = [root]
        assigned.add(root)
        members: list[str] = []
        while stack:
            current = stack.pop()
            members.append(current)
            for parent in reverse.get(current, ()):
                if parent in nodes and parent not in assigned:
                    assigned.add(parent)
                    stack.append(parent)
        components.append(tuple(sorted(members)))

    for node in reversed(order):
        if node not in assigned:
            collect(node)
    return [component for component in components if len(component) > 1]


def test_package_level_cycles_match_frozen_baseline() -> None:
    components = frozenset(_strongly_connected_components(_build_graph()))
    added = sorted(component for component in components - BASELINE)
    removed = sorted(component for component in BASELINE - components)
    assert not added and not removed, (
        "包级依赖环发生变化。\n"
        f"新增环（请拆分或显式登记）: {added}\n"
        f"已消除环（请同步删除基线）: {removed}\n"
        f"当前全部环: {sorted(components)}"
    )
