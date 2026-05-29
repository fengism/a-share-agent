from __future__ import annotations

from app.adapters.content import ContentBlock

_MAX_TEXT_LENGTH = 1800


def _text(value: object) -> str:
    text = "" if value is None else str(value).strip()
    return text or "-"


def _chunks(value: object) -> list[str]:
    text = _text(value)
    return [text[i:i + _MAX_TEXT_LENGTH] for i in range(0, len(text), _MAX_TEXT_LENGTH)] or ["-"]


def _rich_text(value: object) -> list[dict]:
    return [{"type": "text", "text": {"content": chunk}} for chunk in _chunks(value)]


def to_notion_blocks(content: list[ContentBlock]) -> list[dict]:
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
