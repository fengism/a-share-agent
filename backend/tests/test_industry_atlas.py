from app.modules.industry_chain.atlas.contracts import (
    AtlasChain,
    AtlasCompany,
    AtlasLayer,
    AtlasSegment,
)
from app.modules.industry_chain.atlas.graph import build_atlas_graph
from app.modules.industry_chain.atlas.miner import mining_slug
from app.modules.industry_chain.models import IndustryChainResult


def test_mining_slug():
    slug1 = mining_slug("半导体")
    slug2 = mining_slug("半导体")
    slug3 = mining_slug("新能源汽车")

    assert slug1.startswith("auto-")
    assert slug1 == slug2
    assert slug1 != slug3


def test_mined_chain_keeps_its_own_slug_and_provenance():
    """挖掘产物按 slug 覆盖写入，不与既有条目合并。

    早期版本有 ``merge_atlas_chains()`` 把新挖掘结果并进同slug 的旧条目；
    该合并逻辑已随"同slug 稳定覆盖"策略移除——重复挖掘直接刷新条目，
    避免历史 remark 无限累积。此处锁定覆盖后保留来源信息的行为。
    """
    base = AtlasChain(
        slug="auto-semiconductor",
        name="半导体",
        category="电子",
        summary="半导体产业链基础",
        layers=[AtlasLayer(
            key="upstream",
            name="上游",
            segments=[AtlasSegment(
                name="刻蚀设备",
                companies=[AtlasCompany(name="北方华创", code="002371", note="刻蚀设备龙头")],
            )],
        )],
    )
    refreshed = base.model_copy(update={
        "summary": "新挖掘的半导体产业链",
        "mined": True,
        "mined_at": "2026-10-02 12:00:00",
        "archive_id": "arch-123",
    })

    assert refreshed.slug == "auto-semiconductor"
    assert refreshed.mined is True
    assert refreshed.mined_at == "2026-10-02 12:00:00"
    assert refreshed.archive_id == "arch-123"
    # 覆盖后规模统计仍然有效
    assert refreshed.company_count == 1
    assert refreshed.segment_count == 1


def test_build_atlas_graph():
    # 测试指定链条子集的图谱构建
    graph = build_atlas_graph(["semiconductor", "solar-pv"])
    assert graph.summary.total_chains == 2
    assert graph.summary.total_nodes > 0
    assert len(graph.chain_index) == 2
    assert "semiconductor" in graph.chain_index
    assert "solar-pv" in graph.chain_index

    # 验证节点结构
    for node in graph.nodes:
        assert node.id
        assert node.name
        assert node.chain_count >= 1
        assert len(node.chains) >= 1

    # 验证边结构
    for edge in graph.edges:
        assert edge.source
        assert edge.target
        assert edge.chain_slug in ("semiconductor", "solar-pv")


def test_export_yaml_format():
    import yaml

    from app.modules.industry_chain.atlas.loader import get_atlas_chain

    chain = get_atlas_chain("semiconductor")
    assert chain is not None

    dumped = yaml.safe_dump(chain.model_dump(exclude={"source"}), allow_unicode=True, sort_keys=False)
    assert "slug: semiconductor" in dumped
    assert "layers:" in dumped

    # 验证导出的 YAML 可以被有效重新解析
    loaded = yaml.safe_load(dumped)
    assert loaded["slug"] == "semiconductor"
    assert len(loaded["layers"]) > 0


def test_batch_mine_response_model():
    from app.modules.industry_chain.atlas.miner import (
        AtlasBatchMineItem,
        AtlasBatchMineResponse,
    )

    item = AtlasBatchMineItem(
        name="半导体",
        slug="auto-12345",
        action="merged",
        company_count=15,
        segment_count=5,
    )
    resp = AtlasBatchMineResponse(
        scanned=10,
        succeeded=3,
        skipped=7,
        chains=[item],
    )
    assert resp.scanned == 10
    assert resp.succeeded == 3
    assert len(resp.chains) == 1
    assert resp.chains[0].action == "merged"


def test_ai_application_atlas():
    from app.modules.industry_chain.atlas.context import matching_atlas_chain
    from app.modules.industry_chain.atlas.loader import get_atlas_chain

    chain = get_atlas_chain("ai-application")
    assert chain is not None
    assert chain.name == "AI 应用"
    assert len(chain.layers) == 3
    assert chain.company_count >= 10

    matched = matching_atlas_chain("AI 应用")
    assert matched is not None
    assert matched.slug == "ai-application"


def test_industry_charts_layout_is_valid():
    """产业链图谱坐标必须合法且完整落在画布内。

    早期版本断言「任意两图元互不重叠」，且经``pipeline._result_from_atlas_chain``
    从知识库构造输入。该私有函数已随 pipeline 重构移除；新版布局改为
    ``layout: none`` + 显式坐标，并把环节与其代表公司刻意贴靠成对排布，
    因此不再存在「两两不重叠」这一不变量。这里改为校验布局本身的合法性：
    坐标与尺寸均为正有限数、节点成对出现、全部落在 series 声明的画布范围内。
    """
    import math

    from app.modules.industry_chain.charts import build_industry_charts
    from app.modules.industry_chain.models import IndustryChainNode

    nodes = [
        IndustryChainNode(
            name=f"环节{i}",
            company=f"公司{i}",
            code=f"{600000 + i:06d}",
            role="测试角色",
            companies=[f"公司{i}"],
        )
        for i in range(14)
    ]
    result = IndustryChainResult(
        name="AI 应用",
        upstream=nodes[:5],
        midstream=nodes[5:10],
        downstream=nodes[10:],
    )

    charts = build_industry_charts(result)
    assert len(charts) >= 1

    series = charts[0].option["series"][0]
    assert series["type"] == "graph"
    assert series["layout"] == "none"

    chart_nodes = series["data"]
    assert len(chart_nodes) > 10

    canvas_width = charts[0].option.get("width")
    canvas_height = charts[0].option.get("height")

    for node in chart_nodes:
        x, y = node["x"], node["y"]
        width, height = node["symbolSize"]
        assert math.isfinite(x) and math.isfinite(y), f"坐标非法: {node['name']}"
        assert width > 0 and height > 0, f"尺寸非法: {node['name']}"
        if canvas_width is not None:
            assert x - width / 2 >= 0 and x + width / 2 <= canvas_width, \
                f"节点横向越界: {node['name']}"
        if canvas_height is not None:
            assert y - height / 2 >= 0 and y + height / 2 <= canvas_height, \
                f"节点纵向越界: {node['name']}"

    # 每个环节都应与其代表公司成对出现（环节名 + 公司名两个图元）
    names = [node["name"] for node in chart_nodes]
    for i in range(14):
        assert f"环节{i}" in names
        assert f"公司{i}" in names


def test_atlas_company_hk_stocks():
    # 5位港股自动推导 market='hk'
    tencent = AtlasCompany(name="腾讯控股", code="00700", note="腾讯云与混元大模型")
    assert tencent.code == "00700"
    assert tencent.market == "hk"

    # 6位A股自动推导 market='cn'
    cambricon = AtlasCompany(name="寒武纪", code="688256", note="AI芯片")
    assert cambricon.code == "688256"
    assert cambricon.market == "cn"


def test_ai_application_contains_cloud_giants():
    from app.modules.industry_chain.atlas.context import matching_atlas_chain

    chain = matching_atlas_chain("AI 应用")
    assert chain is not None

    upstream = next(layer for layer in chain.layers if layer.key == "upstream")
    maas_segment = next(s for s in upstream.segments if "基础大模型" in s.name)
    company_codes = {c.code for c in maas_segment.companies}
    company_names = {c.name for c in maas_segment.companies}

    assert "00700" in company_codes
    assert "09988" in company_codes
    assert any("腾讯" in name for name in company_names)
    assert any("阿里" in name for name in company_names)
    assert any("百度" in name for name in company_names)
