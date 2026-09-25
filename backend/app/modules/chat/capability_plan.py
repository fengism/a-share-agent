from __future__ import annotations

import re
from collections.abc import Collection
from dataclasses import dataclass

from app.agentic.agents.catalog import list_agent_profiles
from app.agentic.bootstrap import register_all_capabilities
from app.agentic.catalog import registry
from app.financial_data.stock.profile.name_map import contains_known_stock_name
from app.modules.chat.routing import (
    build_keyword_matcher,
    classify_message,
    extract_stock_codes,
    is_url_message,
)

_URL_PATTERN = re.compile(r"https?://[^\s<>()]+", re.I)
_SCREENING_COMPATIBLE_STOCK_KEYWORDS = (
    "个股", "股价", "财报", "财务", "roe", "营收", "净利润", "k线", "macd",
    "rsi", "kdj", "技术面", "基本面", "新闻", "公告", "舆情", "情绪", "风险",
    "止损", "仓位", "目标价", "支撑位", "压力位", "走势", "对比",
)
_SCREENING_KEYWORD_MATCHER = build_keyword_matcher(_SCREENING_COMPATIBLE_STOCK_KEYWORDS)
@dataclass(frozen=True, slots=True)
class ChatCapabilityPlan:
    enabled_skill_names: tuple[str, ...]
    active_skill_names: tuple[str, ...]
    tool_names: tuple[str, ...]
    candidate_agent_names: tuple[str, ...]
    needs_llm_classification: bool
    requires_tool_evidence: bool
    reasoning: str


def _detect_skill_names(message: str) -> set[str]:
    message_without_urls = _URL_PATTERN.sub(" ", message)
    skills = {skill.name: skill for skill in registry.list_skills()}
    detected = {
        skill.name
        for skill in skills.values()
        if skill.name not in {"url_content", "twitter_account"}
        and skill.matches(message_without_urls)
    }
    if extract_stock_codes(message_without_urls) or contains_known_stock_name(message_without_urls):
        detected.add("stock_analysis")
    has_stock_code = bool(extract_stock_codes(message_without_urls))
    has_explicit_stock_analysis = _SCREENING_KEYWORD_MATCHER(message_without_urls)
    if (
        "stock_screening" in detected
        and not has_stock_code
        and not has_explicit_stock_analysis
    ):
        detected.discard("stock_analysis")

    twitter_skill = skills.get("twitter_account")
    if twitter_skill is not None and twitter_skill.matches(message_without_urls):
        detected.add("twitter_account")
    elif is_url_message(message):
        detected.add("url_content")
    return detected


def build_chat_capability_plan(
    message: str,
    *,
    enabled_skill_names: Collection[str] | None = None,
    enabled_agent_names: Collection[str] | None = None,
) -> ChatCapabilityPlan:
    register_all_capabilities()
    requested_skills = None if enabled_skill_names is None else set(enabled_skill_names)
    enabled_skills = tuple(
        skill.name
        for skill in registry.list_skills()
        if requested_skills is None or skill.name in requested_skills
    )
    detected_skills = _detect_skill_names(message)
    active_skills = tuple(name for name in enabled_skills if name in detected_skills)
    tool_names = tuple(registry.get_tool_names_for_skills(active_skills))

    requested_agents = None if enabled_agent_names is None else set(enabled_agent_names)
    available_profiles = tuple(
        profile
        for profile in list_agent_profiles()
        if requested_agents is None or profile.name in requested_agents
    )
    available_agents = tuple(profile.name for profile in available_profiles)
    profiles_by_name = {profile.name: profile for profile in available_profiles}
    decision = classify_message(message, available_agents)
    active_skill_set = set(active_skills)
    candidate_agents = tuple(
        agent_name
        for agent_name in decision.agents
        if agent_name in profiles_by_name
        and set(profiles_by_name[agent_name].skill_names).intersection(active_skill_set)
    )
    if candidate_agents:
        candidate_skills = {
            skill_name
            for agent_name in candidate_agents
            for skill_name in profiles_by_name[agent_name].skill_names
            if skill_name in enabled_skills
        }
        active_skills = tuple(dict.fromkeys((*active_skills, *candidate_skills)))
        tool_names = tuple(registry.get_tool_names_for_skills(active_skills))

    requires_evidence = bool(active_skills and tool_names)
    reasoning = decision.reasoning if candidate_agents else (
        "根据消息意图激活数据 Skill" if active_skills else "未命中数据能力，使用通用对话"
    )
    return ChatCapabilityPlan(
        enabled_skill_names=enabled_skills,
        active_skill_names=active_skills,
        tool_names=tool_names,
        candidate_agent_names=candidate_agents,
        needs_llm_classification=decision.needs_llm_classification and bool(candidate_agents),
        requires_tool_evidence=requires_evidence,
        reasoning=reasoning,
    )
