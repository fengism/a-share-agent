"""前端能力预设与后端能力目录的跨端契约。

``frontend/src/utils/capabilityPresets.ts`` 里的 skill / agent 名是硬编码的。后端改名或
下线某项能力时，前端预设会**静默残缺**——用户点「快速分析」拿到的能力集少了东西，
界面上没有任何提示。

前端侧已在拿到完整目录时调用 ``reportPresetCatalogDrift`` 告警（写入控制台），但那要
等到有人打开「账号能力配置」页。本测试把漂移提前到 CI 阶段，直接变成失败。
"""

from __future__ import annotations

import re
from pathlib import Path

import pytest

from app.modules.chat.capabilities import build_chat_capabilities

PRESET_TS = Path(__file__).resolve().parents[2] / "frontend" / "src" / "utils" / "capabilityPresets.ts"

#: 匹配 ``const PRESET_ACTIVE_SKILLS: SomeType = { ... };`` 的花括号内容（容忍类型标注变化）
_BLOCK_PATTERN = r"const {name}\s*:[^=]*=\s*\{{(.*?)\n\}};"
_STRING_LITERAL_PATTERN = r'"([^"]+)"'

#: ``"all"`` / ``[]`` 是选择规则本身，不是能力名
_NON_NAME_LITERALS = frozenset({"all"})

_SKILLS_BLOCK = "PRESET_ACTIVE_SKILLS"
_AGENTS_BLOCK = "PRESET_ACTIVE_AGENTS"


def _read_preset_source() -> str:
    assert PRESET_TS.is_file(), f"未找到前端预设文件，契约测试失效: {PRESET_TS}"
    return PRESET_TS.read_text(encoding="utf-8")


def _declared_names(block_name: str) -> set[str]:
    """从前端预设文件里抽出某个选择规则块中声明的能力名。"""
    match = re.search(_BLOCK_PATTERN.format(name=block_name), _read_preset_source(), re.DOTALL)
    assert match is not None, (
        f"未能从 {PRESET_TS.name} 解析出 {block_name}；"
        "文件结构可能已变化，请同步本测试的解析逻辑（否则契约会假绿）"
    )
    return {
        name
        for name in re.findall(_STRING_LITERAL_PATTERN, match.group(1))
        if name not in _NON_NAME_LITERALS
    }


@pytest.fixture(scope="module")
def backend_catalog() -> tuple[set[str], set[str]]:
    capabilities = build_chat_capabilities()
    return {skill.name for skill in capabilities.skills}, {agent.name for agent in capabilities.agents}


def test_preset_parser_is_not_silently_empty() -> None:
    """自测：解析逻辑失效时必须让本测试失败，而不是让下面的契约断言在空集上通过。"""
    assert _declared_names(_SKILLS_BLOCK), f"{_SKILLS_BLOCK} 未解析出任何能力名"
    assert _declared_names(_AGENTS_BLOCK), f"{_AGENTS_BLOCK} 未解析出任何能力名"


def test_declared_preset_skills_exist_in_backend_catalog(backend_catalog: tuple[set[str], set[str]]) -> None:
    catalog_skills, _ = backend_catalog
    declared = _declared_names(_SKILLS_BLOCK)
    missing = sorted(declared - catalog_skills)
    assert missing == [], (
        f"前端预设引用了后端不存在的能力名: {missing}。"
        f"要么修正 frontend/src/utils/capabilityPresets.ts，要么确认后端能力是否被改名/下线。"
        f"当前后端 skill 目录: {sorted(catalog_skills)}"
    )


def test_declared_preset_agents_exist_in_backend_catalog(backend_catalog: tuple[set[str], set[str]]) -> None:
    _, catalog_agents = backend_catalog
    declared = _declared_names(_AGENTS_BLOCK)
    missing = sorted(declared - catalog_agents)
    assert missing == [], (
        f"前端预设引用了后端不存在的 Agent 名: {missing}。"
        f"当前后端 agent 目录: {sorted(catalog_agents)}"
    )


def test_backend_catalog_is_not_empty(backend_catalog: tuple[set[str], set[str]]) -> None:
    """自测：目录构建失败时不应让上面的「差集为空」静默通过。"""
    catalog_skills, catalog_agents = backend_catalog
    assert catalog_skills, "后端 skill 目录为空，契约测试失去意义"
    assert catalog_agents, "后端 agent 目录为空，契约测试失去意义"
