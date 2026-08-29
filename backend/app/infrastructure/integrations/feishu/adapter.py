from __future__ import annotations

from app.domain.content import ContentBlock


def _text_element(content: str) -> dict:
    """构造飞书文档块中的文本元素。

    Param:
        content: 文本内容
    Return:
        飞书文本元素 dict，包含 text_run 字段
    """
    return {"text_run": {"content": content, "text_element_style": {}}}


def _heading_block(level: int, text: str) -> dict:
    """构造飞书文档的标题块。

    Param:
        level: 标题层级（1-3）
        text: 标题文本
    Return:
        飞书标题块 dict，block_type 为 3/4/5
    """
    # Feishu: block_type 3=heading1, 4=heading2, 5=heading3
    block_type = level + 2
    heading_key = f"heading{level}"
    return {
        "block_type": block_type,
        heading_key: {"elements": [_text_element(text)], "style": {}},
    }


def to_feishu_doc_blocks(content: list[ContentBlock]) -> list[dict]:
    """将统一的 ContentBlock 列表转换为飞书文档 API 所需的块结构。

    Param:
        content: 通用 ContentBlock 列表
    Return:
        飞书文档块 dict 列表，可直接写入 Docx API
    """
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


def _first_after_heading(
    content: list[ContentBlock],
    heading: str,
    block_type: str,
) -> str:
    in_section = False
    for block in content:
        if block.type == "heading":
            if in_section:
                return ""
            in_section = block.text == heading
            continue
        if in_section and block.type == block_type and block.text.strip():
            return block.text.strip()
    return ""


def _markdown_element(content: str) -> dict:
    return {"tag": "div", "text": {"tag": "lark_md", "content": content}}


def _truncate_card_text(text: str, limit: int = 3000) -> str:
    if len(text) <= limit:
        return text
    boundary = text.rfind("\n", 0, limit - 1)
    if boundary < limit // 2:
        boundary = limit - 1
    return f"{text[:boundary].rstrip()}\n…"


def to_feishu_card(data_type: str, title: str, content: list[ContentBlock], doc_url: str) -> dict:
    """根据数据类型构造飞书消息卡片 payload。

    Param:
        data_type: 数据类型，影响图标和卡片结构，取值 "daily_review"/"analysis"/"chat"/"industry_chain"
        title: 卡片标题
        content: ContentBlock 列表
        doc_url: 关联的飞书文档链接
    Return:
        飞书交互式消息卡片 dict
    """
    icon = (
        "📊" if data_type == "daily_review"
        else "📈" if data_type == "analysis"
        else "🏭" if data_type == "industry_chain"
        else "💬"
    )

    if data_type == "chat":
        lines: list[str] = []
        for b in content:
            if b.type == "heading":
                lines.append(f"**{b.text}**")
            elif b.type == "bullet":
                lines.append(f"- {b.text}")
            else:
                lines.append(b.text)
        body_text = _truncate_card_text("\n".join(lines))
        card = {
            "header": {
                "template": "blue",
                "title": {"tag": "plain_text", "content": f"{icon} {title}"},
            },
            "elements": [
                _markdown_element(body_text),
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
            extra_elements.append(_markdown_element(second_line))
        if strategy_text:
            extra_elements.append(_markdown_element(f"**策略：** {strategy_text}"))
    elif data_type == "analysis":
        metrics = paragraphs[1] if len(paragraphs) > 1 else ""
        action = _first_after_heading(content, "行动与持续跟踪", "paragraph")
        risk = _first_after_heading(content, "风险提示", "bullet")
        if metrics:
            extra_elements.append(_markdown_element(f"**关键指标**\n{metrics}"))
        if action:
            extra_elements.append(_markdown_element(f"**行动建议**\n{action}"))
        if risk:
            extra_elements.append(_markdown_element(f"**首要风险**\n{risk}"))
    else:
        second_line = paragraphs[1] if len(paragraphs) > 1 else ""
        if second_line:
            extra_elements.append(_markdown_element(second_line))

    card = {
        "header": {
            "template": "blue",
            "title": {"tag": "plain_text", "content": f"{icon} {title}"},
        },
        "elements": [
            _markdown_element(f"**核心结论**\n{summary}" if data_type == "analysis" else summary),
            *extra_elements,
            {"tag": "action", "actions": [
                {"tag": "button", "text": {"tag": "plain_text", "content": "📄 查看完整报告"}, "url": doc_url, "type": "primary"},
            ]},
        ],
    }
    return card
