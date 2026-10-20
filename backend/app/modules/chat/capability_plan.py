from __future__ import annotations

import logging
import re
from collections.abc import Collection
from dataclasses import dataclass

from app.agentic.catalog import registry
from app.agentic_integration.agents.catalog import list_agent_profiles
from app.agentic_integration.bootstrap import register_all_capabilities
from app.core.metrics import metrics
from app.modules.chat.routing import (
    build_keyword_matcher,
    classify_message,
    extract_stock_codes,
    is_url_message,
)
from app.modules.chat.stock_reference import mentions_stock_target, needs_stock_resolution

logger = logging.getLogger(__name__)

_URL_PATTERN = re.compile(r"https?://[^\s<>()]+", re.I)
# Layer C：只识别出股票语境、没识别出标的时给的中间分。
# 高于关键词得分（让它进入首轮工具集，拿到 search_stocks），低于已确认标的的 100。
_UNRESOLVED_STOCK_SCORE = 50
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
    initial_skill_names: tuple[str, ...]
    tool_names: tuple[str, ...]
    active_tool_names: tuple[str, ...]
    enabled_tool_names: tuple[str, ...]
    candidate_agent_names: tuple[str, ...]
    needs_llm_classification: bool
    requires_tool_evidence: bool
    # Layer C：消息指向具体证券但未识别出标的，需要先 search_stocks 消歧。
    needs_stock_resolution: bool
    reasoning: str


def _detect_skill_scores(message: str) -> dict[str, int]:
    message_without_urls = _URL_PATTERN.sub(" ", message)
    normalized_message = message_without_urls.lower()
    skills = {skill.name: skill for skill in registry.list_skills()}
    scores: dict[str, int] = {}
    for skill in skills.values():
        if skill.name in {"url_content", "twitter_account"}:
            continue
        score = skill.match_score(normalized_message)
        if score > 0:
            scores[skill.name] = score

    has_stock_code = bool(extract_stock_codes(message_without_urls))
    has_stock_reference = mentions_stock_target(message_without_urls)
    if has_stock_code or has_stock_reference:
        scores["stock_analysis"] = max(scores.get("stock_analysis", 0), 100)
    elif "stock_analysis" in skills and needs_stock_resolution(message_without_urls):
        # 有标的语境但认不出是哪只：给中间分，让它进首轮工具集拿到 search_stocks。
        # 是否真的请求消歧由 build_chat_capability_plan 决定并打点（那里才知道
        # 后续筛选是否把 stock_analysis 又拿掉了）。
        scores["stock_analysis"] = max(
            scores.get("stock_analysis", 0), _UNRESOLVED_STOCK_SCORE
        )
    has_explicit_stock_analysis = _SCREENING_KEYWORD_MATCHER(message_without_urls)
    if (
        "stock_screening" in scores
        and not has_stock_code
        and not has_explicit_stock_analysis
    ):
        scores.pop("stock_analysis", None)

    twitter_skill = skills.get("twitter_account")
    if twitter_skill is not None and twitter_skill.match_score(normalized_message) > 0:
        scores["twitter_account"] = max(scores.get("twitter_account", 0), 100)
    elif is_url_message(message):
        scores["url_content"] = max(scores.get("url_content", 0), 100)
    return scores


def _detect_skill_names(message: str) -> set[str]:
    return set(_detect_skill_scores(message))


def _select_initial_skills(
    active_skills: tuple[str, ...],
    *,
    max_initial: int,
) -> tuple[str, ...]:
    if max_initial < 0:
        return active_skills
    if max_initial == 0:
        return ()
    return active_skills[:max_initial]


def _initial_tool_names(
    skill_names: tuple[str, ...],
    *,
    core_tools_enabled: bool,
    max_tools: int = 0,
) -> tuple[str, ...]:
    """首轮工具清单：按 Skill 相关度顺序取，``max_tools>0`` 时截断。

    截断依赖顺序正确（`CapabilityCatalog._selected_skills` 保留调用方顺序）；否则
    查新闻时会把 ``web_search`` 排在后面而被先截掉。被截掉的工具不是消失——模型仍可
    通过 ``load_skill`` 拿到，所以这是一个纯粹的「首轮 schema 体积」开关。
    """
    if core_tools_enabled:
        names = registry.get_initial_tool_names_for_skills(skill_names)
    else:
        names = registry.get_tool_names_for_skills(skill_names)
    if max_tools > 0 and len(names) > max_tools:
        metrics.record_agentic_event("skill_initial_tools_capped")
        logger.info(
            "首轮工具数被 chat_max_initial_tools 截断: %s -> %s（skills=%s）",
            len(names),
            max_tools,
            ",".join(skill_names),
        )
        names = names[:max_tools]
    return tuple(names)


def build_chat_capability_plan(
    message: str,
    *,
    enabled_skill_names: Collection[str] | None = None,
    enabled_agent_names: Collection[str] | None = None,
    max_initial_active_skills: int = 3,
    core_tools_enabled: bool = True,
    max_initial_tools: int = 0,
) -> ChatCapabilityPlan:
    register_all_capabilities()
    requested_skills = None if enabled_skill_names is None else set(enabled_skill_names)
    enabled_skills = tuple(
        skill.name
        for skill in registry.list_skills()
        if requested_skills is None or skill.name in requested_skills
    )
    detected_scores = _detect_skill_scores(message)
    priority_by_name = {skill.name: skill.priority for skill in registry.list_skills()}

    def sort_key(name: str) -> tuple[int, int, str]:
        return (-detected_scores.get(name, 0), priority_by_name.get(name, 100), name)

    active_skills = tuple(
        sorted(
            (name for name in enabled_skills if name in detected_scores),
            key=sort_key,
        )
    )
    initial_skills = _select_initial_skills(
        active_skills,
        max_initial=max_initial_active_skills,
    )
    tool_names = _initial_tool_names(
        initial_skills, core_tools_enabled=core_tools_enabled, max_tools=max_initial_tools
    )
    active_tool_names = tuple(registry.get_tool_names_for_skills(active_skills))
    enabled_tool_names = tuple(registry.get_tool_names_for_skills(enabled_skills))

    requested_agents = None if enabled_agent_names is None else set(enabled_agent_names)
    available_profiles = tuple(
        profile
        for profile in list_agent_profiles()
        if requested_agents is None or profile.name in requested_agents
    )
    available_agents = tuple(profile.name for profile in available_profiles)
    profiles_by_name = {profile.name: profile for profile in available_profiles}
    decision = classify_message(message, available_agents)
    # 候选 Agent 的筛选依据是「关键词已激活的 Skill」，必须用合并前的快照；
    # 而下面判断消歧时要用合并后的最终 active_skills，不要复用这份快照。
    detected_skill_set = set(active_skills)
    candidate_agents = tuple(
        agent_name
        for agent_name in decision.agents
        if agent_name in profiles_by_name
        and set(profiles_by_name[agent_name].skill_names).intersection(detected_skill_set)
    )
    if candidate_agents:
        candidate_skills = {
            skill_name
            for agent_name in candidate_agents
            for skill_name in profiles_by_name[agent_name].skill_names
            if skill_name in enabled_skills
        }
        if candidate_skills:
            for skill_name in candidate_skills:
                detected_scores.setdefault(skill_name, 0)
            active_skills = tuple(
                sorted(
                    dict.fromkeys((*active_skills, *candidate_skills)),
                    key=sort_key,
                )
            )
            initial_skills = _select_initial_skills(
                active_skills,
                max_initial=max_initial_active_skills,
            )
            tool_names = _initial_tool_names(
                initial_skills,
                core_tools_enabled=core_tools_enabled,
                max_tools=max_initial_tools,
            )
            active_tool_names = tuple(registry.get_tool_names_for_skills(active_skills))

    # 证据门看的是「这次是否真的启用了数据 Skill」，而不是首轮工具集：
    # ``chat_max_initial_active_skills=0`` 只下发 load_skill 时 tool_names 为空，
    # 若拿它当依据，证据门会被配置静默关掉。
    requires_evidence = bool(active_skills and active_tool_names)
    # 与 _detect_skill_scores 用同一份去 URL 文本：URL 里的数字不能被当成股票代码，
    # 否则会出现“分数已按未识别提振、却没有下发消歧指令”的不一致。
    message_without_urls = _URL_PATTERN.sub(" ", message)
    unresolved_stock = (
        "stock_analysis" in set(active_skills)
        and not extract_stock_codes(message_without_urls)
        and needs_stock_resolution(message_without_urls)
    )
    if unresolved_stock:
        metrics.record_agentic_event("stock_resolution_requested")
    if len(initial_skills) < len(active_skills):
        metrics.record_agentic_event("skill_initial_converged")
    if not initial_skills and active_skills:
        metrics.record_agentic_event("skill_initial_empty")
    reasoning = decision.reasoning if candidate_agents else (
        "根据消息意图激活数据 Skill" if active_skills else "未命中数据能力，使用通用对话"
    )
    return ChatCapabilityPlan(
        enabled_skill_names=enabled_skills,
        active_skill_names=active_skills,
        initial_skill_names=initial_skills,
        tool_names=tool_names,
        active_tool_names=active_tool_names,
        enabled_tool_names=enabled_tool_names,
        candidate_agent_names=candidate_agents,
        needs_llm_classification=decision.needs_llm_classification and bool(candidate_agents),
        requires_tool_evidence=requires_evidence,
        needs_stock_resolution=unresolved_stock,
        reasoning=reasoning,
    )
