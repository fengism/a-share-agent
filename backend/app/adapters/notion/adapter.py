from __future__ import annotations

from app.adapters.content import ContentBlock

_MAX_TEXT_LENGTH = 1800


def _text(value: object) -> str:
    """将任意值规范化为非空字符串。

    Param:
        value: 待转换的值
    Return:
        去除首尾空白的字符串，空值返回 "-"
    """
    text = "" if value is None else str(value).strip()
    return text or "-"


def _chunks(value: object) -> list[str]:
    """将文本按 Notion 单块长度上限切分。

    Param:
        value: 待切分的文本值
    Return:
        切分后的字符串列表，至少包含一个元素
    """
    text = _text(value)
    return [text[i:i + _MAX_TEXT_LENGTH] for i in range(0, len(text), _MAX_TEXT_LENGTH)] or ["-"]


def _rich_text(value: object) -> list[dict]:
    """构造 Notion rich_text 数组。

    Param:
        value: 待包装的文本值
    Return:
        Notion rich_text 元素 dict 列表
    """
    return [{"type": "text", "text": {"content": chunk}} for chunk in _chunks(value)]


def to_notion_blocks(content: list[ContentBlock]) -> list[dict]:
    """将统一的 ContentBlock 列表转换为 Notion 块结构。

    Param:
        content: 通用 ContentBlock 列表
    Return:
        Notion 块 dict 列表，可直接用于 Notion API 的 children 字段
    """
    blocks: list[dict] = []
    for block in content:
        if block.type == "heading":
            block_type = f"heading_{block.level}"
            blocks.append({"object": "block", "type": block_type, block_type: {"rich_text": _rich_text(block.text)}})
        elif block.type == "paragraph":
            blocks.append({"object": "block", "type": "paragraph", "paragraph": {"rich_text": _rich_text(block.text)}})
        elif block.type == "bullet":
            blocks.append({"object": "block", "type": "bulleted_list_item", "bulleted_list_item": {"rich_text": _rich_text(block.text)}})
        elif block.type == "divider":
            blocks.append({"object": "block", "type": "divider", "divider": {}})
    return blocks
