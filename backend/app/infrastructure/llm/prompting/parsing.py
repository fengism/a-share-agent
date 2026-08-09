import json
import re
from typing import TypeVar

from pydantic import BaseModel

OutputT = TypeVar("OutputT", bound=BaseModel)


def extract_json_object(text: str) -> str:
    """从代码围栏或额外说明中提取 JSON 对象。"""
    match = re.search(r"```(?:json)?\s*\n?(.*?)\n?```", text, re.DOTALL)
    if match:
        return match.group(1).strip()
    start = text.find("{")
    end = text.rfind("}")
    if start != -1 and end > start:
        return text[start:end + 1]
    return text.strip()


def parse_model_response(raw_text: str, output_model: type[OutputT]) -> OutputT:
    """解析 JSON 并用指定 Pydantic 模型执行契约校验。"""
    payload = json.loads(extract_json_object(raw_text))
    return output_model.model_validate(payload)
