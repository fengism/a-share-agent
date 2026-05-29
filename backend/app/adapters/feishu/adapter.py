from __future__ import annotations

from app.adapters.content import ContentBlock


def _text_element(content: str) -> dict:
    return {"text_run": {"content": content, "text_element_style": {}}}


def _heading_block(level: int, text: str) -> dict:
    # Feishu: block_type 3=heading1, 4=heading2, 5=heading3
    block_type = level + 2
    heading_key = f"heading{level}"
    return {
        "block_type": block_type,
        heading_key: {"elements": [_text_element(text)], "style": {}},
    }


def to_feishu_doc_blocks(content: list[ContentBlock]) -> list[dict]:
    blocks: list[dict] = []
    for block in content:
        text = block.text or "-"
        if block.type == "heading":
            blocks.append(_heading_block(block.level, text))
        elif block.type == "paragraph":
            blocks.append({
                "block_type": 2,
                "text": {"elements": [_text_element(text)], "style": {}},
            })
        elif block.type == "bullet":
            blocks.append({
                "block_type": 12,
                "bullet": {"elements": [_text_element(text)], "style": {}},
            })
        elif block.type == "divider":
            blocks.append({"block_type": 22, "divider": {}})
    return blocks


def to_feishu_card(data_type: str, title: str, content: list[ContentBlock], doc_url: str) -> dict:
    icon = "📊" if data_type == "daily_review" else "📈" if data_type == "analysis" else "💬"

    if data_type == "chat":
        lines: list[str] = []
        for b in content:
            if b.type == "heading":
                lines.append(f"**{b.text}**")
            elif b.type == "bullet":
                lines.append(f"- {b.text}")
            else:
                lines.append(b.text)
        body_text = "\n".join(lines)[:3000]
        card = {
            "header": {"title": {"tag": "plain_text", "content": f"{icon} {title}"}},
            "elements": [
                {"tag": "div", "text": {"tag": "lark_md", "content": body_text}},
            ],
        }
        return card

    paragraphs = [b.text for b in content if b.type == "paragraph"]
    summary = paragraphs[0] if paragraphs else "-"

    extra_elements: list[dict] = []
    if data_type == "daily_review":
        second_line = paragraphs[1] if len(paragraphs) > 1 else ""
        strategy_bullets = [b.text for b in content if b.type == "bullet"]
        strategy_text = strategy_bullets[0] if strategy_bullets else ""
        if second_line:
            extra_elements.append({"tag": "div", "text": {"tag": "lark_md", "content": second_line}})
        if strategy_text:
            extra_elements.append({"tag": "div", "text": {"tag": "lark_md", "content": f"**策略:** {strategy_text}"}})
    else:
        second_line = paragraphs[1] if len(paragraphs) > 1 else ""
        if second_line:
            extra_elements.append({"tag": "div", "text": {"tag": "lark_md", "content": second_line}})

    card = {
        "header": {"title": {"tag": "plain_text", "content": f"{icon} {title}"}},
        "elements": [
            {"tag": "div", "text": {"tag": "lark_md", "content": summary}},
            *extra_elements,
            {"tag": "action", "actions": [
                {"tag": "button", "text": {"tag": "plain_text", "content": "📄 查看完整报告"}, "url": doc_url, "type": "primary"},
            ]},
        ],
    }
    return card
