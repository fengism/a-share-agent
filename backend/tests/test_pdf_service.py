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


def test_generate_industry_chain_pdf_html_full_features():
    from app.modules.industry_chain.models import IndustryChainNode, IndustryChainRelationship

    result = IndustryChainResult(
        name="智能电网特高压",
        summary="电网投资与特高压出海双轮驱动。",
        key_stocks=[
            IndustryChainNode(
                code="600406",
                name="国电南瑞",
                business_relevance="earnings",
                role="二次设备龙头，调度系统市占率第一",
                total_market_cap="1850.5亿",
                pe="22.4",
                pb="3.1",
            )
        ],
        relationships=[
            IndustryChainRelationship(
                source_node="特高压交流变压器",
                target_node="特高压换流站工程",
                relation_type="supply",
                impact_direction="positive",
                title="主网设备交付带动工程节点确认",
                time_lag="2-3个季度",
                target_metric="特高压主网设备月度中标额",
                tracking_metrics=["国网月度招标统计", "变压器出厂排产率"],
            )
        ],
    )
    html = generate_industry_chain_pdf_html(result)

    # 目录导航与跨页分页样式
    assert "📑 报告目录" in html
    assert "page-break-inside: avoid" in html
    assert "display: table-header-group" in html

    # 标的估值与业务关联标签
    assert "业绩兑现" in html
    assert "国电南瑞" in html
    assert "600406" in html
    assert "总市值: 1850.5亿" in html
    assert "PE: 22.4" in html

    # 传导时滞与跟踪指标
    assert "传导滞后期：" in html
    assert "2-3个季度" in html
    assert "观测指标：" in html
    assert "特高压主网设备月度中标额" in html
    assert "高频跟踪指标：" in html
    assert "国网月度招标统计、变压器出厂排产率" in html



