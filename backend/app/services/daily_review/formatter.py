import json


def _unwrap_json_block(value: str) -> str:
    """去除 Markdown 代码块围栏（```），保留代码块内的文本。

    Param:
        value: 原始字符串
    Return:
        去除围栏后的字符串
    """
    text = value.strip()
    if text.startswith("```") and text.endswith("```"):
        lines = text.splitlines()
        if len(lines) >= 2:
            return "\n".join(lines[1:-1]).strip()
    return text


def _stringify_review_value(value) -> str:
    """将 LLM 返回的 JSON 值（dict/list/scalar）转换为 Markdown 文本。

    Param:
        value: 任意 JSON 兼容值
    Return:
        Markdown 格式的字符串
    """
    if value is None:
        return ""
    if isinstance(value, list):
        return "\n".join(f"- {_stringify_review_value(item)}" for item in value)
    if isinstance(value, dict):
        return "\n".join(f"- **{key}**：{_stringify_review_value(item)}" for key, item in value.items())
    return str(value)


def normalize_llm_review(value: str) -> str:
    """规范化 LLM 返回的复盘文本：尝试解析 JSON 并格式化为 Markdown，解析失败则原样返回。

    Param:
        value: LLM 返回的原始字符串
    Return:
        规范化后的 Markdown 字符串
    """
    text = _unwrap_json_block(value)
    try:
        parsed = json.loads(text)
    except json.JSONDecodeError:
        return value
    if isinstance(parsed, dict):
        return "\n\n".join(
            f"## {key}\n\n{_stringify_review_value(item)}" for key, item in parsed.items()
        )
    return _stringify_review_value(parsed)
