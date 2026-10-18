"""新浪接口响应格式解析。"""

import json
from typing import cast


def parse_jsonp(text: str) -> dict:
    payload = text.strip()
    if payload.startswith("var "):
        start = payload.find("(")
        end = payload.rfind(")")
        if start == -1 or end <= start:
            raise ValueError("新浪分时 JSONP 格式无效")
        payload = payload[start + 1 : end]
    return cast(dict, json.loads(payload))
