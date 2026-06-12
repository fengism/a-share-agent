"""Orchestrator._resolve_stocks 路由精确化测试。"""

from app.services.chat.tools import stock_helpers
from app.services.chat.orchestrator import Orchestrator


class TestResolveStocks:
    def setup_method(self):
        self.orch = Orchestrator()

    async def test_no_stock_intent_returns_empty(self, monkeypatch):
        """无股票意图的消息（如「今天大盘怎么样」）不应注入任何个股上下文。"""
        async def fake_search(query: str):
            # 即便底层模糊搜索匹配到无关个股，也应被名称过滤拦掉
            return [{"code": "000001", "name": "平安银行"}]

        async def fake_info(code: str):
            return {"name": "平安银行", "industry": "银行", "market_cap": "1万亿", "pe": 5.0}

        monkeypatch.setattr(stock_helpers, "search_stocks", fake_search)
        monkeypatch.setattr(stock_helpers, "get_stock_info", fake_info)

        ctx = await self.orch._resolve_stocks("今天大盘怎么样")
        assert ctx == ""

    async def test_explicit_code_resolved(self, monkeypatch):
        """消息含 6 位代码时应按代码精确解析并注入基本信息（不走模糊搜索）。"""
        async def fake_search(query: str):
            raise AssertionError("有明确代码时不应调用 search_stocks")

        async def fake_info(code: str):
            return {"name": "贵州茅台", "industry": "白酒", "market_cap": "2万亿", "pe": 30.0}

        monkeypatch.setattr(stock_helpers, "search_stocks", fake_search)
        monkeypatch.setattr(stock_helpers, "get_stock_info", fake_info)

        ctx = await self.orch._resolve_stocks("分析一下 600519")
        assert "600519" in ctx
        assert "贵州茅台" in ctx

    async def test_name_in_message_resolved(self, monkeypatch):
        """消息含完整股票名时应解析。"""
        async def fake_search(query: str):
            return [{"code": "600519", "name": "贵州茅台"}]

        async def fake_info(code: str):
            return {"name": "贵州茅台", "industry": "白酒", "market_cap": "2万亿", "pe": 30.0}

        monkeypatch.setattr(stock_helpers, "search_stocks", fake_search)
        monkeypatch.setattr(stock_helpers, "get_stock_info", fake_info)

        ctx = await self.orch._resolve_stocks("贵州茅台怎么样")
        assert "贵州茅台" in ctx

    async def test_fuzzy_mismatch_filtered(self, monkeypatch):
        """名称未字面出现在消息中的模糊匹配结果应被过滤。"""
        async def fake_search(query: str):
            return [{"code": "000001", "name": "平安银行"}]

        async def fake_info(code: str):
            return {"name": "平安银行", "industry": "银行", "market_cap": "1万亿", "pe": 5.0}

        monkeypatch.setattr(stock_helpers, "search_stocks", fake_search)
        monkeypatch.setattr(stock_helpers, "get_stock_info", fake_info)

        ctx = await self.orch._resolve_stocks("帮我看看保险板块的机会")
        assert ctx == ""
