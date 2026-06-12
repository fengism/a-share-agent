from __future__ import annotations

import asyncio
import json
import logging
import re
from collections.abc import AsyncGenerator
from dataclasses import dataclass

from openai import AsyncOpenAI

from app.config import get_settings
from app.models.chat import ChatMessage, ChatStreamDelta
from app.services.chat.skills import register_all_skills
from app.services.chat.subagents.base import SharedToolCache, SubAgentResult
from app.services.chat.subagents.prompts import (
    DECISION_SYNTHESIS_PROMPT,
    ORCHESTRATOR_CLASSIFY_PROMPT,
)
from app.services.chat.subagents.technical import create_technicalagent
from app.services.chat.subagents.fundamental import create_fundamentalagent
from app.services.chat.subagents.news import create_newsagent
from app.services.chat.subagents.risk import create_riskagent
from app.services.chat.subagents.macro import create_macro_agent
from app.services.llm.client import create_async_openai_chat_runtime

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

_ALL_AGENTS = ["technical", "fundamental", "news", "risk", "macro"]
_URL_PATTERN = re.compile(r'https?://\S+', re.IGNORECASE)


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
        """多 Agent 编排主流程：路由 → 并发执行子 Agent（工具调用实时可见）→ 综合分析。

        Param:
            message: 用户消息
            history: 历史消息列表，可选
        Return:
            产生 ChatStreamDelta 事件的异步生成器
        """
        runtime = create_async_openai_chat_runtime(get_settings())
        llm_client = runtime.client
        model = runtime.model

        # URL 消息直接回退到 legacy agent（拥有 fetch_url 工具），
        # 避免 URL 中的 6 位数字被误匹配为股票代码而路由到子 Agent。
        if _URL_PATTERN.search(message):
            from app.services.chat.agent import _run_legacy_agent
            async for delta in _run_legacy_agent(message, history):
                yield delta
            return

        decision = self._keyword_classify(message)
        logger.info(f"Keyword classify: agents={decision.agents}, stock_codes={decision.stock_codes}")

        if not decision.agents:
            from app.services.chat.agent import _run_legacy_agent
            async for delta in _run_legacy_agent(message, history):
                yield delta
            return

        # 仅当关键词无法精确判断（落到全部 5 个 Agent 的兜底）时才用 LLM 二次分类，
        # 关键词已明确匹配的场景直接执行，省去一次阻塞式 LLM 往返以降低首字延迟。
        all_agents = list(self.sub_agents.keys())
        if decision.is_complex and set(decision.agents) == set(all_agents):
            try:
                decision = await self._llm_classify(message, llm_client, model)
                logger.info(f"LLM classify: agents={decision.agents}")
            except Exception as e:
                logger.warning(f"LLM classify failed, using all agents: {e}")
                decision = RoutingDecision(agents=all_agents,
                                           stock_codes=decision.stock_codes, is_complex=True)

        yield ChatStreamDelta(type="text", content="🔍 正在进行多维度分析...\n\n")

        # 前置股票识别：一次性解析股票代码和基本信息，注入给所有子 Agent
        stock_context = await self._resolve_stocks(message)
        enriched_message = (stock_context + "\n\n" + message) if stock_context else message

        results: dict[str, SubAgentResult] = {}
        async for delta in self._run_sub_agents_streaming(
            decision.agents, enriched_message, history, llm_client, model, results
        ):
            yield delta

        yield ChatStreamDelta(type="text", content="\n🧠 正在综合分析...\n\n")

        async for token in self._synthesize(message, results, llm_client, model):
            yield ChatStreamDelta(type="text", content=token)

        yield ChatStreamDelta(type="done")

    async def _resolve_stocks(self, message: str) -> str:
        """前置股票识别：解析消息中的股票并返回格式化上下文。

        路由精确化：优先用 6 位代码精确解析；无代码时才走名称搜索，且仅接受
        股票名（或其去掉常见后缀的核心名）字面出现在消息中的结果，过滤拼音/模糊误匹配，
        避免「今天大盘怎么样」这类无个股意图的消息被误注入无关股票。

        Param:
            message: 用户原始消息
        Return:
            格式化的股票上下文字符串，无股票时返回空字符串
        """
        from app.services.chat.tools.stock_helpers import search_stocks, get_stock_info

        codes = _STOCK_CODE_PATTERN.findall(message)
        if codes:
            # 有明确代码：按代码精确解析（最多 3 只），不做模糊搜索
            stocks = [{"code": c, "name": ""} for c in dict.fromkeys(codes)][:3]
        else:
            search_result = await search_stocks(query=message)
            if isinstance(search_result, dict) and search_result.get("error"):
                return ""
            if not search_result:
                return ""
            candidates = search_result if isinstance(search_result, list) else [search_result]
            # 仅保留名称（或核心名）字面出现在消息中的结果，过滤拼音/模糊误匹配
            stocks = [s for s in candidates if self._name_in_message(s.get("name", ""), message)][:3]
            if not stocks:
                return ""

        lines = ["[股票信息预解析 — 已获取代码和基本信息，后续分析直接使用，无需再次搜索]"]
        for s in stocks:
            code = s.get("code", s.get("symbol", ""))
            name = s.get("name", "")
            if not code:
                continue
            info = await get_stock_info(code=code)
            if isinstance(info, dict) and not info.get("error"):
                name = name or info.get("name", "")
                industry = info.get("industry", "")
                market_cap = info.get("market_cap", info.get("total_market_value", ""))
                pe = info.get("pe", info.get("pe_ttm", ""))
                lines.append(f"- {name}（{code}）：行业={industry}，市值={market_cap}，PE={pe}")
            else:
                lines.append(f"- {name}（{code}）")

        return "\n".join(lines) if len(lines) > 1 else ""

    @staticmethod
    def _name_in_message(name: str, message: str) -> bool:
        """判断股票名是否字面出现在消息中（含去掉常见后缀的核心名）。

        Param:
            name: 股票名称
            message: 用户原始消息
        Return:
            名称或其核心名出现在消息中返回 True
        """
        name = (name or "").strip()
        if not name:
            return False
        if name in message:
            return True
        # 去掉 A/B/股份/集团/科技 等常见后缀后再比对核心名，至少 2 字才算匹配
        core = re.sub(r"(股份|集团|科技|控股|实业|发展|国际|A|B)$", "", name)
        return len(core) >= 2 and core in message

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

    async def _llm_classify(self, message: str, llm_client: AsyncOpenAI, model: str) -> RoutingDecision:
        messages = [
            {"role": "system", "content": "你是一个意图分类器。只返回JSON，不要任何其他内容。"},
            {"role": "user", "content": ORCHESTRATOR_CLASSIFY_PROMPT + "\n\n用户消息: " + message},
        ]
        response = await llm_client.chat.completions.create(
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

    async def _run_sub_agents_streaming(
        self, agent_names: list[str], message: str,
        history: list[ChatMessage] | None,
        llm_client: AsyncOpenAI, model: str,
        results: dict[str, SubAgentResult],
    ) -> AsyncGenerator[ChatStreamDelta, None]:
        """并发执行子 Agent，实时 yield 各 Agent 的工具调用/结果增量，最终把结果写入 results。

        Param:
            agent_names: 待执行的子 Agent 名称列表
            message: 用户消息
            history: 历史消息列表，可选
            llm_client: 异步 OpenAI 客户端
            model: 模型名称
            results: 用于收集各子 Agent 结果的字典（原地填充）
        Return:
            产生 ChatStreamDelta 事件的异步生成器（text/tool_call/tool_result）
        """
        names = [n for n in agent_names if n in self.sub_agents]
        queue: asyncio.Queue = asyncio.Queue()
        _DONE = object()
        # 跨子 Agent 共享工具缓存：估值/技术指标等被多个 Agent 共用的数据只抓一次
        tool_cache = SharedToolCache()

        async def run_one(name: str) -> None:
            """运行单个子 Agent，向队列推送归属标题与工具增量，完成后存入 results。"""
            agent = self.sub_agents[name]
            await queue.put(ChatStreamDelta(type="text", content=f"\n🔧 **{agent.display_name}**\n"))
            try:
                res = await agent.run(message, history, llm_client, model,
                                      event_queue=queue, tool_cache=tool_cache)
            except asyncio.CancelledError:
                raise
            except Exception as e:
                logger.error(f"SubAgent {name} failed: {e}")
                res = SubAgentResult(
                    agent_name=name,
                    display_name=agent.display_name,
                    analysis=f"分析失败: {e}",
                    errors=[str(e)],
                )
            results[name] = res
            await queue.put(ChatStreamDelta(
                type="text", content=f"✅ {agent.display_name} 完成（{res.duration_ms}ms）\n"
            ))
            await queue.put(_DONE)

        tasks = [asyncio.create_task(run_one(n)) for n in names]
        remaining = len(tasks)
        try:
            while remaining > 0:
                item = await queue.get()
                if item is _DONE:
                    remaining -= 1
                    continue
                yield item
        finally:
            # 消费者提前关闭（客户端断开）时取消未完成的子 Agent，避免泄漏
            for t in tasks:
                if not t.done():
                    t.cancel()
            await asyncio.gather(*tasks, return_exceptions=True)

    async def _synthesize(self, message: str, results: dict[str, SubAgentResult],
                          llm_client: AsyncOpenAI, model: str) -> AsyncGenerator[str, None]:
        parts = [f"## {r.display_name}\n{r.analysis}" for r in results.values()]
        synthesis_input = f"用户问题: {message}\n\n" + "\n\n".join(parts)

        messages = [
            {"role": "system", "content": DECISION_SYNTHESIS_PROMPT},
            {"role": "user", "content": synthesis_input},
        ]
        try:
            stream = await llm_client.chat.completions.create(
                model=model,
                messages=messages,
                temperature=0.1,
                stream=True,
            )
            async for chunk in stream:
                if chunk.choices and chunk.choices[0].delta.content:
                    yield chunk.choices[0].delta.content
        except Exception as e:
            logger.error(f"Synthesis LLM call failed: {e}")
            yield f"\n综合分析生成失败: {e}\n"
            for r in results.values():
                yield f"\n### {r.display_name}\n{r.analysis}\n"
