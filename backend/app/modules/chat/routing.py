from __future__ import annotations

import re
from collections.abc import Callable, Collection
from dataclasses import dataclass

from pydantic import BaseModel, Field

from app.agentic.runtime.llm import create_chat_completion
from app.infrastructure.llm.prompting.parsing import extract_json_object
from app.infrastructure.llm.tool_calling import AsyncLLMClient
from app.modules.chat.prompts import (
    ORCHESTRATOR_CLASSIFY_PROMPT,
    ORCHESTRATOR_CLASSIFY_PROMPT_REF,
)

DEFAULT_AGENT_NAMES = ("technical", "fundamental", "news", "risk", "macro")

_KEYWORD_MAP: dict[str, tuple[str, ...]] = {
    "technical": (
        "K线", "K 线", "MACD", "RSI", "KDJ", "布林", "技术面", "均线", "趋势",
        "支撑", "压力", "量价", "金叉", "死叉", "k线",
    ),
    "fundamental": (
        "PE", "PB", "估值", "财报", "财务", "ROE", "营收", "基本面",
        "市盈率", "市净率", "净利润", "分红", "选股", "筛选", "小于", "大于",
    ),
    "news": ("新闻", "研报", "公告", "舆情", "热度", "情绪", "利好", "利空", "消息"),
    "risk": ("风险", "止损", "仓位", "波动", "回撤", "预警", "风险评估"),
    "macro": (
        "CPI", "PPI", "PMI", "M0", "M1", "M2", "GDP", "宏观", "通胀",
        "通缩", "货币供应", "降准", "降息", "利率", "货币政策", "经济数据",
    ),
}

_FULL_ANALYSIS_KEYWORDS = ("分析", "综合", "评估", "深度", "全面", "诊断")
# 边界 + A股板块前缀，避免金额、日期等任意 6 位数字被当成股票代码
_STOCK_CODE_PATTERN = re.compile(
    r"(?<![0-9])(?:(?:60|68|00|30|43|83|87|88)\d{4}|(?:200|920)\d{3})(?![0-9])"
)
_URL_PATTERN = re.compile(r"https?://\S+", re.IGNORECASE)
_URL_ONLY_PATTERN = re.compile(r"^\s*(?:https?://\S+\s*)+$", re.IGNORECASE)
_GREETING_PATTERN = re.compile(
    r"^(你好|hi|hello|hey|嗨|谢谢|感谢|好的|ok|再见|拜拜|嗯|哦|啊|是的|对的|知道了|收到|辛苦了|麻烦了)[!！。.?\s]*$",
    re.IGNORECASE,
)


def build_keyword_matcher(keywords: Collection[str]) -> Callable[[str], bool]:
    """英文缩写（PE/ROE/MACD 等）用 ASCII 词边界匹配，中文关键词用子串匹配。"""
    ascii_keywords = sorted(
        {keyword for keyword in keywords if keyword.isascii() and keyword.isalnum()}
    )
    text_keywords = sorted(
        {keyword for keyword in keywords if keyword not in ascii_keywords}
    )
    pattern = (
        re.compile(
            "(?<![A-Za-z0-9])(?:"
            + "|".join(re.escape(keyword) for keyword in ascii_keywords)
            + ")(?![A-Za-z0-9])",
            re.IGNORECASE,
        )
        if ascii_keywords
        else None
    )

    def matches(message: str) -> bool:
        if pattern is not None and pattern.search(message):
            return True
        lowered = message.lower()
        return any(keyword.lower() in lowered for keyword in text_keywords)

    return matches


_KEYWORD_MATCHERS: dict[str, Callable[[str], bool]] = {
    agent_name: build_keyword_matcher(keywords)
    for agent_name, keywords in _KEYWORD_MAP.items()
}


@dataclass
class RoutingDecision:
    agents: list[str]
    needs_llm_classification: bool = False
    reasoning: str = ""


class _RoutingOutput(BaseModel):
    agents: list[str] = Field(default_factory=list, max_length=5)
    reasoning: str = Field(default="模型完成分析维度路由", max_length=500)


def is_url_message(message: str) -> bool:
    return _URL_PATTERN.search(message) is not None


def is_url_only_message(message: str) -> bool:
    return _URL_ONLY_PATTERN.match(message) is not None


def is_greeting_message(message: str) -> bool:
    return _GREETING_PATTERN.match(message.strip()) is not None


def extract_stock_codes(message: str) -> list[str]:
    return _STOCK_CODE_PATTERN.findall(message)


def classify_message(
    message: str,
    available_agents: Collection[str] = DEFAULT_AGENT_NAMES,
) -> RoutingDecision:
    available = set(available_agents)
    matched_domains = [
        agent_name
        for agent_name, matches in _KEYWORD_MATCHERS.items()
        if matches(message)
    ]
    matched_agents = [agent_name for agent_name in matched_domains if agent_name in available]
    agent_names = [name for name in DEFAULT_AGENT_NAMES if name in available]
    has_stock_code = bool(extract_stock_codes(message))

    if not matched_domains and not has_stock_code:
        if any(keyword in message for keyword in _FULL_ANALYSIS_KEYWORDS):
            return RoutingDecision(
                agents=agent_names,
                reasoning="用户要求综合分析",
            )
        return RoutingDecision(agents=[], reasoning="未命中专业分析路由")

    if matched_domains:
        return RoutingDecision(
            agents=matched_agents,
            reasoning="根据领域关键词选择 Agent",
        )

    return RoutingDecision(
        agents=agent_names,
        needs_llm_classification=True,
        reasoning="仅识别到股票代码，需要模型判断分析维度",
    )


async def classify_with_llm(
    message: str,
    llm_client: AsyncLLMClient,
    model: str,
    available_agents: Collection[str] = DEFAULT_AGENT_NAMES,
) -> RoutingDecision:
    messages = [
        {"role": "system", "content": "你是一个意图分类器。只返回JSON，不要任何其他内容。"},
        {"role": "user", "content": ORCHESTRATOR_CLASSIFY_PROMPT + "\n\n用户消息: " + message},
    ]
    response = await create_chat_completion(
        llm_client,
        model=model,
        messages=messages,
        temperature=0.0,
        max_tokens=512,
        stream=False,
        response_format={"type": "json_object"},
        metric_stage=ORCHESTRATOR_CLASSIFY_PROMPT_REF,
    )
    content = response.choices[0].message.content or "{}"
    data = _RoutingOutput.model_validate_json(extract_json_object(content))
    agent_names = list(available_agents)
    agents = [agent for agent in data.agents if agent in agent_names]
    if not agents:
        agents = agent_names
    return RoutingDecision(
        agents=agents,
        reasoning=data.reasoning,
    )
