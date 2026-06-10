from app.services.chat.orchestrator import Orchestrator, RoutingDecision


class TestKeywordClassifier:
    def setup_method(self):
        self.orch = Orchestrator()

    def test_technical_query_routes_to_technical(self):
        d = self.orch._keyword_classify("查一下600519的K线走势")
        assert d.agents == ["technical"]
        assert d.is_complex is False

    def test_fundamental_query_routes_to_fundamental(self):
        d = self.orch._keyword_classify("600519的PE和估值情况")
        assert d.agents == ["fundamental"]
        assert d.is_complex is False

    def test_news_query_routes_to_news(self):
        d = self.orch._keyword_classify("贵州茅台最近有什么新闻")
        assert d.agents == ["news"]
        assert d.is_complex is False

    def test_risk_query_routes_to_risk(self):
        d = self.orch._keyword_classify("600519的风险评估和止损位")
        assert d.agents == ["risk"]
        assert d.is_complex is False

    def test_full_analysis_routes_to_all(self):
        d = self.orch._keyword_classify("深度分析一下贵州茅台")
        assert set(d.agents) == {"technical", "fundamental", "news", "risk", "macro"}
        assert d.is_complex is True

    def test_non_stock_query_returns_empty(self):
        d = self.orch._keyword_classify("今天天气怎么样")
        assert d.agents == []

    def test_multi_domain_query_is_complex(self):
        d = self.orch._keyword_classify("600519的估值和新闻")
        assert "fundamental" in d.agents
        assert "news" in d.agents
        assert d.is_complex is True

    def test_stock_code_extraction(self):
        d = self.orch._keyword_classify("分析一下600519的技术面")
        assert "600519" in d.stock_codes

    def test_technical_keywords_case_insensitive(self):
        d = self.orch._keyword_classify("看看macd指标")
        assert "technical" in d.agents

    def test_vague_analysis_keyword_triggers_all(self):
        d = self.orch._keyword_classify("帮我分析一下这只股票")
        assert set(d.agents) == {"technical", "fundamental", "news", "risk", "macro"}
