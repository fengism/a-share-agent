"""Document-oriented discovery plans, not an N-metrics × N-tools query expansion."""

from __future__ import annotations

import json
from dataclasses import asdict, dataclass

from app.domain.industry_chain import IndustryChainResearchScope, resolve_industry_chain_scope
from app.modules.industry_chain.templates import select_research_template

DOCUMENT_SEARCH_RULES = """## 文献级检索规划
- 分开两张清单：研究问题/指标是读正文的提取清单；query是寻找一份资料的入口，不能一指标一query。
- 第一阶段按资料包规划，通常先定位行业全景/技术报告、需求侧原始披露、代表公司定期报告；候选不是必跑任务。
- 一个资料包可以覆盖多个相邻维度：市场规模、竞争格局和技术路线可来自同份行业报告；同一家公司的收入、订单、产能、毛利和现金流优先读同份定期报告。
- query采用“主题或公司 + 文献/披露主题 + 必要年份”，只保留少量区分词。不机械拼接所有指标、区域、上下游、公司和年份，不做笛卡尔积展开；也不要退化为泛泛的“发展前景分析”。
- 先选择一个发现工具；已定位资料则读正文/目录/相关章节，不再换搜索工具重复寻找同份资料。只有来源不可读、陈旧、范围不符或需独立交叉核对时才换源，并说明原因。
- 正文逐篇整理“已覆盖问题、具体片段、仍缺的关键前提”。同一原文可覆盖多项研究问题，但重复引用不能算多个独立来源。
- 只有阅读后仍影响核心判断的缺口，才发起一个针对该缺口的窄查询。先查已有正文/续读/PDF相关页，再查新材料；不要把所有missing维度逐项变成query。
- A股优先get_stock_documents定位定期报告。keyword是标题过滤，不要填收入/良率/客户等正文指标；报告期不能从标题猜测，应读原文确认。
- 资料包和候选词是计划，不是事实、已执行工具或已有证据。遵守实际时间/地域/公司范围，原文不能取得时如实留缺口。
"""

_FOCUS = {
    "robot": (
        "产业技术白皮书",
        "商业化应用报告",
        ("单机成本与部件价值量", "技术路线与关键部件", "竞争与量产阶段"),
        ("付费任务", "交付与复购", "任务经济性"),
    ),
    "ai_computing": (
        "基础设施产业报告",
        "数据中心建设运营报告",
        ("规模与需求", "计算网络散热配置", "供应瓶颈与竞争"),
        ("资本开支", "机柜交付", "计费利用率"),
    ),
    "baijiu": (
        "行业运行报告",
        "消费渠道调研报告",
        ("市场规模", "价格带与竞争", "渠道结构"),
        ("终端动销", "渠道库存与批价", "经销商回款"),
    ),
    "solar": (
        "产业发展路线图",
        "装机运行报告",
        ("环节价格成本", "产能与技术路线", "行业竞争"),
        ("装机需求", "消纳与项目收益", "组件采购"),
    ),
    "semiconductor": (
        "产业技术白皮书",
        "终端市场报告",
        ("产业结构与竞争", "制程与封装", "产能与库存周期"),
        ("终端销量", "客户库存", "采购与资本开支"),
    ),
    "pharma": (
        "行业运行报告",
        "药品准入市场报告",
        ("管线与竞争", "审批与商业化", "研发产业链"),
        ("准入与处方", "销售回款", "临床及商业化约束"),
    ),
}


@dataclass(frozen=True)
class SourcePackage:
    key: str
    query: str
    read_for: tuple[str, ...]
    route: str


def source_packages(name: str, scope: IndustryChainResearchScope) -> tuple[SourcePackage, ...]:
    scope = resolve_industry_chain_scope(scope)
    template = select_research_template(name)
    landscape, demand, coverage, demand_coverage = (
        _FOCUS[template.key]
        if template.key in _FOCUS
        else (
            "产业研究报告",
            "需求应用报告",
            ("产业边界", "市场与竞争", "技术及上下游结构"),
            ("真实需求", "客户采购", "经营约束"),
        )
    )
    year = scope.end_date.year
    return (
        SourcePackage(
            "landscape", f"{name} {landscape} {year}", coverage, "先用一个发现工具定位综合原文，再按多个相关问题阅读"
        ),
        SourcePackage(
            "demand", f"{name} {demand} {year}", demand_coverage, "优先客户/行业机构原始披露；已被首份文献覆盖则不另搜"
        ),
        SourcePackage(
            "company",
            "",
            ("相关业务收入", "订单与产能", "毛利与现金流"),
            "根据已读材料选2-3家代表公司；A股用get_stock_documents(kind=periodic_report)；其他公司定位官方定期报告，每家同份报告集中阅读，不逐指标搜索",
        ),
    )


def render_discovery_plan(name: str, scope: IndustryChainResearchScope) -> str:
    scope = resolve_industry_chain_scope(scope)
    packages = source_packages(name, scope)
    return (
        "资料包候选（通常先选2个发现query，再按实际资料需要定位公司文档；不是硬性调用顺序）：\n"
        + json.dumps([asdict(package) for package in packages], ensure_ascii=False)
        + f"\n筛选口径：region={scope.region}，{scope.start_date}至{scope.end_date}，基准日={scope.as_of_date}。"
        "地域和日期优先用工具筛选或正文口径核对，不为每个字段复制查询。"
        "年份仅用于定位基准日之前已发布材料；该年度完整报告尚未发布时选最近已披露版本，不查未来报告。"
        "找到具体来源再使用其实际URL，不猜链接、报告结论或公司代码。"
    )


def render_repair_reading_plan(targets) -> str:
    """Group extraction tasks without dropping any of the actual validation targets."""
    packages: dict[str, dict] = {}
    for target in targets:
        if target.key.startswith("company:"):
            key = target.key
            action = "同一公司：先复用现有目录/已读定期报告，集中查业务、订单、产能与财务章节；目录没有可用链接才重新定位文档"
        elif target.key.startswith("source:"):
            key = target.key
            action = "同一证据组：优先重核已有原文或续读，不把不同断言各生成搜索词"
        else:
            key = "chain_dossier"
            action = "上下游与传导问题合并为一份链条阅读任务；先查已有全景/需求文献的相关章节，缺核心前提才拆窄查询"
        entry = packages.setdefault(key, {"key": key, "action": action, "read_for": []})
        entry["read_for"].append(target.question)
    return "补证阅读任务（不是逐项query，全部原核验目标仍需检查）：\n" + json.dumps(
        list(packages.values()), ensure_ascii=False
    )
