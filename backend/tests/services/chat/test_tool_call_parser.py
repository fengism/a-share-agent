from app.services.chat.skills import register_all_skills, registry
from app.services.chat.tool_call_parser import extract_pseudo_tool_calls


register_all_skills()


def test_extract_pseudo_tool_call_with_query_and_limit():
    calls = extract_pseudo_tool_calls('iwencai_select_stock("PE小于20的白酒股", 15)', registry)

    assert len(calls) == 1
    assert calls[0].function.name == "iwencai_select_stock"
    assert calls[0].function.arguments == '{"query": "PE小于20的白酒股", "limit": 15}'


def test_extract_pseudo_tool_call_with_single_query():
    calls = extract_pseudo_tool_calls('iwencai_select_stock("PE小于20的白酒股")', registry)

    assert len(calls) == 1
    assert calls[0].function.arguments == '{"query": "PE小于20的白酒股"}'


def test_extract_pseudo_tool_call_ignores_unknown_function():
    calls = extract_pseudo_tool_calls('unknown_tool("PE小于20的白酒股", 15)', registry)

    assert calls == []


def test_extract_pseudo_tool_call_ignores_normal_text():
    calls = extract_pseudo_tool_calls('下面是 PE 小于 20 的白酒股分析结果。', registry)

    assert calls == []
