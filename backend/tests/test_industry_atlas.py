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


def test_newly_added_atlas_chains():
    from app.modules.industry_chain.atlas.context import matching_atlas_chain

    # 1. CPO光模块
    cpo_chain = matching_atlas_chain("CPO光模块")
    assert cpo_chain is not None
    assert cpo_chain.slug == "cpo-optical-module"
    assert any("光芯片" in seg.name for layer in cpo_chain.layers for seg in layer.segments)
    assert any(c.code == "300308" for layer in cpo_chain.layers for seg in layer.segments for c in seg.companies)

    # 2. 固态电池
    ssb_chain = matching_atlas_chain("固态电池")
    assert ssb_chain is not None
    assert ssb_chain.slug == "solid-state-battery"
    assert any("固态电解质" in seg.name for layer in ssb_chain.layers for seg in layer.segments)
    assert any(c.name == "当升科技" for layer in ssb_chain.layers for seg in layer.segments for c in seg.companies)

    # 3. 商业航天
    aero_chain = matching_atlas_chain("商业航天")
    assert aero_chain is not None
    assert aero_chain.slug == "commercial-aerospace"
    assert any("相控阵" in seg.name for layer in aero_chain.layers for seg in layer.segments)
    assert any(c.code == "600118" for layer in aero_chain.layers for seg in layer.segments for c in seg.companies)


def test_user_private_atlas_lifecycle(tmp_path, monkeypatch):
    from app.modules.industry_chain.atlas.context import matching_atlas_chain
    from app.modules.industry_chain.atlas.loader import (
        build_atlas_catalog,
        delete_user_atlas_chain,
        get_atlas_chain,
    )
    from app.modules.industry_chain.atlas.miner import save_mined_chain

    monkeypatch.setattr("app.modules.industry_chain.atlas.loader.DATA_DIR", tmp_path)

    user_id = 999
    chain = AtlasChain(
        slug="user-my-quantum",
        name="量子计算定制链",
        category="个人专属",
        summary="用户专属量子计算知识库",
        layers=[
            AtlasLayer(
                key="upstream",
                name="核心器件",
                segments=[
                    AtlasSegment(
                        name="超导量子芯片",
                        companies=[AtlasCompany(name="国盾量子", code="688027", note="量子通信龙头")],
                    )
                ],
            )
        ],
    )

    # 1. 存入私有知识库
    save_mined_chain(chain, user_id=user_id)

    # 2. 普通用户可获取私有条目，source 为 user
    user_chain = get_atlas_chain("user-my-quantum", user_id=user_id)
    assert user_chain is not None
    assert user_chain.name == "量子计算定制链"
    assert user_chain.source == "user"

    # 其他用户无法获取
    other_chain = get_atlas_chain("user-my-quantum", user_id=888)
    assert other_chain is None

    # 3. catalog 包含个人专属分类与条目
    catalog = build_atlas_catalog(user_id=user_id)
    assert any(c.slug == "user-my-quantum" and c.source == "user" for c in catalog.chains)
    assert "个人专属" in catalog.categories

    # 4. matching_atlas_chain 优先匹配用户私有图谱
    matched = matching_atlas_chain("量子计算定制链", user_id=user_id)
    assert matched is not None
    assert matched.slug == "user-my-quantum"
    assert matched.source == "user"

    # 5. 删除私有条目
    assert delete_user_atlas_chain("user-my-quantum", user_id=user_id) is True
    assert get_atlas_chain("user-my-quantum", user_id=user_id) is None
    # 重复删除返回 False
    assert delete_user_atlas_chain("user-my-quantum", user_id=user_id) is False


def test_api_private_atlas_permissions_and_mine(tmp_path, monkeypatch):
    from fastapi.testclient import TestClient

    from app.api.auth.dependencies import require_active_user
    from app.main import app
    from app.modules.industry_chain.models import IndustryChainNode, IndustryChainResult
    from app.modules.industry_chain.persistence.repository import save_industry_chain

    monkeypatch.setattr("app.modules.industry_chain.atlas.loader.DATA_DIR", tmp_path)
    monkeypatch.setattr("app.modules.industry_chain.persistence.repository._DATA_DIR", tmp_path / "industry_chains")

    user_regular = {"id": 1001, "username": "trader", "is_admin": False, "role": "user"}

    app.dependency_overrides[require_active_user] = lambda: user_regular

    # 保存一份通过质量门（complete）的产业链分析存档供挖掘
    nodes_up = [
        IndustryChainNode(name="刻蚀设备", company="北方华创", code="002371", role="设备龙头", companies=["北方华创"]),
        IndustryChainNode(name="光刻胶", company="彤程新材", code="603650", role="材料龙头", companies=["彤程新材"]),
    ]
    nodes_mid = [
        IndustryChainNode(name="芯片制造", company="中芯国际", code="688981", role="代工龙头", companies=["中芯国际"]),
    ]
    result = IndustryChainResult(
        name="测试专用链",
        upstream=nodes_up,
        midstream=nodes_mid,
        downstream=[],
        quality_status="complete",
    )
    save_industry_chain("测试专用链", result, user_id=1001, archive_id="arch-001")

    try:
        with TestClient(app) as client:
            # 1. 普通用户请求 scope="global" 报错 403
            resp = client.post("/api/industry-chain/atlas/mine", json={"name": "测试专用链", "scope": "global"})
            assert resp.status_code == 403
            assert "仅管理员可沉淀为全局公共知识库" in resp.json()["message"]

            # 2. 普通用户挖掘（默认 scope="user"）成功，返回 source="user"
            resp = client.post("/api/industry-chain/atlas/mine", json={"name": "测试专用链"})
            assert resp.status_code == 200
            data = resp.json()
            assert data["source"] == "user"
            assert data["name"] == "测试专用链"
            slug = data["slug"]

            # 3. 普通用户查看目录能看到自己的专属图谱
            catalog_resp = client.get("/api/industry-chain/atlas/chains")
            assert catalog_resp.status_code == 200
            chains = catalog_resp.json()["chains"]
            assert any(c["slug"] == slug and c["source"] == "user" for c in chains)

            # 4. 普通用户可以删除自己的私有图谱
            del_resp = client.delete(f"/api/industry-chain/atlas/chains/{slug}")
            assert del_resp.status_code == 200

            # 5. 普通用户尝试删除全局内置链（semiconductor），报错 403
            del_global = client.delete("/api/industry-chain/atlas/chains/semiconductor")
            assert del_global.status_code == 403

            # 6. 普通用户导入 YAML 测试（支持私有知识库导入，阻断 global 导入）
            sample_yaml = """
slug: user-custom-yaml
name: 自定义光子计算
category: 个人专属
summary: 自定义导入的私有知识库
layers:
  - key: upstream
    name: 上游
    segments:
      - name: 光芯片
        companies:
          - name: 中际旭创
            code: "300308"
"""
            # 传 scope="global" 报错 403
            imp_global = client.post("/api/industry-chain/atlas/import", json={"content": sample_yaml, "scope": "global"})
            assert imp_global.status_code == 403

            # 正常导入，作为个人专属
            imp_user = client.post("/api/industry-chain/atlas/import", json={"content": sample_yaml})
            assert imp_user.status_code == 200
            imported_chains = imp_user.json()
            assert len(imported_chains) == 1
            assert imported_chains[0]["source"] == "user"
            assert imported_chains[0]["slug"] == "user-custom-yaml"
    finally:
        app.dependency_overrides.pop(require_active_user, None)


async def test_build_mined_chain_enriches_segment_description_and_notes(monkeypatch):
    from unittest.mock import AsyncMock
    from app.modules.industry_chain.atlas.miner import build_mined_chain
    from app.modules.industry_chain.models import IndustryChainNode, IndustryChainResult

    mock_name_map = AsyncMock(return_value={"002371": "北方华创", "688012": "中微公司", "600584": "长电科技"})
    monkeypatch.setattr("app.modules.industry_chain.atlas.miner.get_stock_name_map", mock_name_map)

    result = IndustryChainResult(
        name="测试集成电路",
        summary="测试芯片产业沉淀",
        upstream=[
            IndustryChainNode(
                name="刻蚀设备",
                role="先进制程干法刻蚀",
                market_share="市占率 40%",
                companies=["北方华创", "中微公司"],
            ),
        ],
        midstream=[
            IndustryChainNode(
                name="晶圆制造",
                role="12寸晶圆制造",
                companies=["北方华创"],
            ),
        ],
        downstream=[
            IndustryChainNode(
                name="芯片封装",
                role="先进倒装与封装",
                companies=["长电科技"],
            ),
        ],
        key_stocks=[
            IndustryChainNode(
                code="002371",
                name="北方华创",
                role="设备龙头",
                benefit_path="受益于晶圆厂扩产及国产化率突破",
                moat="高深宽比刻蚀与ICP技术壁垒",
            ),
        ],
    )

    chain = await build_mined_chain(result, user_id=1)
    assert chain is not None
    assert chain.source == "user"
    assert chain.slug.startswith("user-")

    # 验证 segment description 沉淀
    upstream_layer = next(l for l in chain.layers if l.key == "upstream")
    segment = upstream_layer.segments[0]
    assert segment.name == "刻蚀设备"
    assert "先进制程干法刻蚀" in segment.description
    assert "市占率 40%" in segment.description

    # 验证 key_stocks 中的 benefit_path 注入为公司 note
    bfhc = next(c for c in segment.companies if c.code == "002371")
    assert bfhc.note == "受益于晶圆厂扩产及国产化率突破"


