from app.modules.industry_chain.models import IndustryChainResult
from app.modules.industry_chain.pdf_service import generate_industry_chain_pdf_html


def test_generate_industry_chain_pdf_html_section_01():
    """战略定位章节：标题与定位正文必须出现在 PDF HTML 中。

    早期版本会在后端把summary 渲染成Markdown（``_markdown_to_html`` + ``**粗体**``），
    该能力已随 presentation 层重构移除，改为前端渲染后传入，因此这里不再断言
    Markdown 标签与 CSS 类名，只锁定仍然存在的章节结构与文本内容。
    """
    result = IndustryChainResult(
        name="AI 应用",
        positioning="处于人工智能全产业链终端价值兑现环节",
        summary="## 核心研判\n**算力是门槛**，应用是终局价值。",
    )
    html = generate_industry_chain_pdf_html(result)

    assert "01 · 战略定位与产业全景概述" in html
    assert "处于人工智能全产业链终端价值兑现环节" in html
    # summary 原文（连同 Markdown 标记）由前端渲染后传入，后端不再二次转换
    assert "算力是门槛" in html
