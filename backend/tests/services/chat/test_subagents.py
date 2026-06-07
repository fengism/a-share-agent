from app.services.chat.subagents.base import SubAgent, SubAgentResult
from app.services.chat.subagents.technical import create_technicalagent
from app.services.chat.subagents.fundamental import create_fundamentalagent
from app.services.chat.subagents.news import create_newsagent
from app.services.chat.subagents.risk import create_riskagent
from app.services.chat.skills import registry


class TestSubAgentCreation:
    def test_technical_agent_has_correct_config(self):
        agent = create_technicalagent()
        assert agent.name == "technical"
        assert agent.display_name == "技术面分析"
        assert "search_stocks" in agent.skill_names
        assert "get_stock_kline" in agent.skill_names
        assert "get_stock_technical_indicators" in agent.skill_names
        assert agent.max_rounds == 3

    def test_fundamental_agent_has_correct_config(self):
        agent = create_fundamentalagent()
        assert agent.name == "fundamental"
        assert "get_stock_info" in agent.skill_names
        assert "get_stock_valuation_detail" in agent.skill_names
        assert "get_stock_financial" in agent.skill_names

    def test_news_agent_has_correct_config(self):
        agent = create_newsagent()
        assert agent.name == "news"
        assert "get_stock_news" in agent.skill_names
        assert "get_stock_sentiment" in agent.skill_names

    def test_risk_agent_has_correct_config(self):
        agent = create_riskagent()
        assert agent.name == "risk"
        assert "get_stock_info" in agent.skill_names
        assert "get_stock_sentiment" in agent.skill_names


class TestSkillRegistryToolDefinitions:
    def test_get_tool_definitions_for_returns_subset(self):
        defs = registry.get_tool_definitions_for(["search_stocks", "get_stock_kline"])
        names = [d["function"]["name"] for d in defs]
        assert "search_stocks" in names
        assert "get_stock_kline" in names
        assert len(names) == 2

    def test_get_tool_definitions_for_empty_list(self):
        defs = registry.get_tool_definitions_for([])
        assert defs == []

    def test_get_tool_definitions_for_nonexistent_skill(self):
        defs = registry.get_tool_definitions_for(["nonexistent_skill"])
        assert defs == []


class TestSubAgentResult:
    def test_result_defaults(self):
        r = SubAgentResult(agent_name="test", display_name="测试", analysis="hello")
        assert r.tools_called == []
        assert r.errors == []
        assert r.duration_ms == 0
