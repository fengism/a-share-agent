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


def test_generate_industry_chain_pdf_html_section_relationships():
    from app.modules.industry_chain.models import IndustryChainRelationship

    result = IndustryChainResult(
        name="CPO光模块",
        summary="CPO技术加速渗透。",
        relationships=[
            IndustryChainRelationship(
                source_node="高速光芯片",
                target_node="800G/1.6T光模块",
                impact_direction="positive",
                relation_type="transmission",
                title="光芯片供给短缺推升模块交付周期",
                detail="上游晶圆代工产能不足制约出货量",
                driver="大模型集群算力采购激增",
                conditions=["良率稳定提升"],
                invalidation="海外新产能超预期投产",
            )
        ],
    )
    html = generate_industry_chain_pdf_html(result)

    assert "05 · 产业链传导机制与利润弹性假定" in html
    assert "高速光芯片 → 800G/1.6T光模块" in html
    assert "正向传导" in html
    assert "上游晶圆代工产能不足制约出货量" in html
    assert "良率稳定提升" in html
    assert "海外新产能超预期投产" in html


