from __future__ import annotations

import asyncio
import json
import logging
import re
from collections.abc import AsyncGenerator
from dataclasses import dataclass

from openai import OpenAI

from app.config import get_settings
from app.models.chat import ChatMessage, ChatStreamDelta
from app.services.chat.message_builder import build_messages
from app.services.chat.skills import register_all_skills
from app.services.chat.subagents.base import SubAgentResult
from app.services.chat.subagents.technical import create_technicalagent
from app.services.chat.subagents.fundamental import create_fundamentalagent
from app.services.chat.subagents.news import create_newsagent
from app.services.chat.subagents.risk import create_riskagent
from app.services.chat.subagents.macro import create_macro_agent
from app.services.llm.client import create_openai_chat_runtime

logger = logging.getLogger(__name__)

# 关键词分类规则
_KEYWORD_MAP: dict[str, list[str]] = {
    "technical": ["K线", "MACD", "RSI", "KDJ", "布林", "技术面", "均线", "趋势", "支撑", "压力", "量价", "金叉", "死叉", "k线"],
    "fundamental": ["PE", "PB", "估值", "财报", "财务", "ROE", "营收", "基本面", "市盈率", "市净率", "净利润", "分红"],
    "news": ["新闻", "研报", "公告", "舆情", "热度", "情绪", "利好", "利空", "消息"],
    "risk": ["风险", "止损", "仓位", "波动", "回撤", "预警", "风险评估"],
    "macro": ["CPI", "PPI", "PMI", "M0", "M1", "M2", "GDP", "宏观", "通胀", "通缩", "货币供应", "降准", "降息", "利率", "货币政策", "经济数据"],
}

_FULL_ANALYSIS_KEYWORDS = ["分析", "综合", "评估", "深度", "全面", "诊断"]
_STOCK_CODE_PATTERN = re.compile(r"\d{6}")

_ORCHESTRATOR_CLASSIFY_PROMPT = """分析用户意图，返回JSON格式的路由决策。

可选代理:
- technical: 技术面分析（K线、MACD、RSI、KDJ、布林带、均线、趋势、支撑压力）
- fundamental: 基本面分析（PE/PB/PS/PEG估值、财报、ROE、营收增长、盈利能力）
- news: 新闻和情绪分析（新闻、研报、公告、舆情、热度、散户情绪）
- risk: 风险评估（风险因素、波动性、回撤风险、止损位、仓位建议）
- macro: 宏观经济分析（CPI、PPI、PMI、M0/M1/M2货币供应量、GDP、通胀通缩、货币政策）

返回严格JSON:
{"agents": ["代理名称"], "stock_codes": ["股票代码"], "reasoning": "路由理由"}

规则:
- 问K线/技术指标/趋势 -> ["technical"]
- 问估值/财报/基本面 -> ["fundamental"]
- 问新闻/研报/舆情 -> ["news"]
- 问风险/止损/仓位 -> ["risk"]
- 问CPI/PPI/PMI/货币供应/宏观/通胀/利率 -> ["macro"]
- 要求全面分析/深度分析/综合评估 -> 全部五个代理
- 多股对比 -> 全部五个代理
- 无法判断 -> 全部五个代理"""

_SYNTHESIS_PROMPT = """你是资深的 A 股投资决策顾问。基于多位专业分析师的分析结果，给出综合投资建议。

## 决策原则
1. 多数维度一致时，信号更强
2. 技术面与基本面冲突时，以基本面为主
3. 风险评估为"高"时，建议需保守
4. 新闻面出现重大利空时，需特别提示
5. 始终保持风险意识，不盲目看多

## 输出格式
使用 Markdown 格式，包含以下部分：

### 📊 综合评分
X/10 分

### 🎯 交易信号
明确给出：强烈买入 / 买入 / 持有观望 / 卖出 / 强烈卖出

### 💰 目标价格区间
XX.XX 元 — XX.XX 元

### 🔍 核心逻辑（3-5 点）

### ⚠️ 主要风险（2-3 点）

### 📝 综合结论
简洁的投资建议总结"""


@dataclass
class RoutingDecision:
    agents: list[str]
    stock_codes: list[str]
    is_complex: bool = False


class Orchestrator:
    def __init__(self):
        register_all_skills()
        self.sub_agents = {
            "technical": create_technicalagent(),
            "fundamental": create_fundamentalagent(),
            "news": create_newsagent(),
            "risk": create_riskagent(),
            "macro": create_macro_agent(),
        }

    async def run(self, message: str, history: list[ChatMessage] | None = None
                  ) -> AsyncGenerator[ChatStreamDelta, None]:
        runtime = create_openai_chat_runtime(get_settings())
        llm_client = runtime.client
        model = runtime.model

        decision = self._keyword_classify(message)
        logger.info(f"Keyword classify: agents={decision.agents}, stock_codes={decision.stock_codes}")

        if not decision.agents:
            from app.services.chat.agent import _run_legacy_agent
            async for delta in _run_legacy_agent(message, history):
                yield delta
            return

        if decision.is_complex or len(decision.agents) > 1:
            try:
                decision = await self._llm_classify(message, llm_client, model)
                logger.info(f"LLM classify: agents={decision.agents}")
            except Exception as e:
                logger.warning(f"LLM classify failed, using all agents: {e}")
                decision = RoutingDecision(agents=["technical", "fundamental", "news", "risk", "macro"],
                                           stock_codes=decision.stock_codes, is_complex=True)

        yield ChatStreamDelta(type="text", content="🔍 正在进行多维度分析...\n\n")

        results = await self._run_sub_agents(decision.agents, message, history, llm_client, model)

        for name, result in results.items():
            yield ChatStreamDelta(type="text", content=f"✅ {result.display_name} 完成（{result.duration_ms}ms）\n")

        yield ChatStreamDelta(type="text", content="\n🧠 正在综合分析...\n\n")

        async for token in self._synthesize(message, results, llm_client, model):
            yield ChatStreamDelta(type="text", content=token)

        yield ChatStreamDelta(type="done")

    def _keyword_classify(self, message: str) -> RoutingDecision:
        msg_lower = message.lower()
        matched_agents: list[str] = []
        for agent_name, keywords in _KEYWORD_MAP.items():
            if any(kw.lower() in msg_lower for kw in keywords):
                matched_agents.append(agent_name)

        stock_codes = _STOCK_CODE_PATTERN.findall(message)

        if not matched_agents and not stock_codes:
            for kw in _FULL_ANALYSIS_KEYWORDS:
                if kw in message:
                    matched_agents = ["technical", "fundamental", "news", "risk", "macro"]
                    return RoutingDecision(agents=matched_agents, stock_codes=stock_codes, is_complex=True)
            return RoutingDecision(agents=[], stock_codes=[])

        if not matched_agents:
            matched_agents = ["technical", "fundamental", "news", "risk", "macro"]
            return RoutingDecision(agents=matched_agents, stock_codes=stock_codes, is_complex=True)

        if len(matched_agents) == 1:
            return RoutingDecision(agents=matched_agents, stock_codes=stock_codes, is_complex=False)

        return RoutingDecision(agents=matched_agents, stock_codes=stock_codes, is_complex=True)

    async def _llm_classify(self, message: str, llm_client: OpenAI, model: str) -> RoutingDecision:
        messages = [
            {"role": "system", "content": "你是一个意图分类器。只返回JSON，不要任何其他内容。"},
            {"role": "user", "content": _ORCHESTRATOR_CLASSIFY_PROMPT + "\n\n用户消息: " + message},
        ]
        response = await asyncio.to_thread(
            llm_client.chat.completions.create,
            model=model,
            messages=messages,
            temperature=0.0,
            stream=False,
        )
        content = response.choices[0].message.content or "{}"
        json_match = re.search(r"\{.*\}", content, re.S)
        if not json_match:
            raise ValueError(f"No JSON in LLM response: {content[:200]}")
        data = json.loads(json_match.group())
        agents = [a for a in data.get("agents", []) if a in self.sub_agents]
        if not agents:
            agents = list(self.sub_agents.keys())
        stock_codes = data.get("stock_codes", [])
        return RoutingDecision(agents=agents, stock_codes=stock_codes, is_complex=True)

    async def _run_sub_agents(self, agent_names: list[str], message: str,
                              history: list[ChatMessage] | None,
                              llm_client: OpenAI, model: str
                              ) -> dict[str, SubAgentResult]:
        tasks = {}
        for name in agent_names:
            if name in self.sub_agents:
                tasks[name] = self.sub_agents[name].run(message, history, llm_client, model)

        gathered = await asyncio.gather(*tasks.values(), return_exceptions=True)
        results: dict[str, SubAgentResult] = {}
        for name, result in zip(tasks.keys(), gathered):
            if isinstance(result, Exception):
                logger.error(f"SubAgent {name} failed: {result}")
                results[name] = SubAgentResult(
                    agent_name=name,
                    display_name=self.sub_agents[name].display_name,
                    analysis=f"分析失败: {result}",
                    errors=[str(result)],
                )
            else:
                results[name] = result
        return results

    async def _synthesize(self, message: str, results: dict[str, SubAgentResult],
                          llm_client: OpenAI, model: str) -> AsyncGenerator[str, None]:
        parts = [f"## {r.display_name}\n{r.analysis}" for r in results.values()]
        synthesis_input = f"用户问题: {message}\n\n" + "\n\n".join(parts)

        messages = [
            {"role": "system", "content": _SYNTHESIS_PROMPT},
            {"role": "user", "content": synthesis_input},
        ]
        try:
            stream = await asyncio.to_thread(
                llm_client.chat.completions.create,
                model=model,
                messages=messages,
                temperature=0.1,
                stream=True,
            )
            for chunk in stream:
                if chunk.choices and chunk.choices[0].delta.content:
                    yield chunk.choices[0].delta.content
        except Exception as e:
            logger.error(f"Synthesis LLM call failed: {e}")
            yield f"\n综合分析生成失败: {e}\n"
            for r in results.values():
                yield f"\n### {r.display_name}\n{r.analysis}\n"
