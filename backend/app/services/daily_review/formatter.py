import json


def _unwrap_json_block(value: str) -> str:
    text = value.strip()
    if text.startswith("```") and text.endswith("```"):
        lines = text.splitlines()
        if len(lines) >= 2:
            return "\n".join(lines[1:-1]).strip()
    return text


def _stringify_review_value(value) -> str:
    if value is None:
        return ""
    if isinstance(value, list):
        return "\n".join(f"- {_stringify_review_value(item)}" for item in value)
    if isinstance(value, dict):
        return "\n".join(f"- **{key}**：{_stringify_review_value(item)}" for key, item in value.items())
    return str(value)


def normalize_llm_review(value: str) -> str:
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
