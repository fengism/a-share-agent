"""海关总署进出口贸易与重点商品出海/进口数据服务。"""

from __future__ import annotations

import logging
import math
from dataclasses import dataclass
from typing import Any, cast

from app.core.cache import market_cache as cache
from app.core.concurrency.rate_limiter import eastmoney_semaphore
from app.infrastructure.providers.provider_gateway import provider_gateway
from app.infrastructure.providers.registry import get_provider

logger = logging.getLogger(__name__)

_CACHE_TTL_SECONDS = 300


@dataclass(frozen=True)
class ExportCommodityProfile:
    category: str
    commodity: str
    trade_type: str  # "出口" or "进口"
    keywords: tuple[str, ...]
    unit: str
    description: str
    key_markets: str
    related_a_stocks: tuple[str, ...]
    industry_chains: tuple[str, ...]


KEY_COMMODITY_PROFILES: tuple[ExportCommodityProfile, ...] = (
    ExportCommodityProfile(
        category="汽车与零部件",
        commodity="汽车（包括底盘）及新能源汽车",
        trade_type="出口",
        keywords=("汽车", "新能源汽车", "电动汽车", "整车", "商用车", "客车", "底盘", "汽配", "汽车零部件"),
        unit="万辆 / 亿美元",
        description="我国制造业出海第一大核心支柱，电动载人汽车（新能源车）与自主品牌出海高增长",
        key_markets="欧洲、东南亚、拉美、中东、中亚",
        related_a_stocks=("比亚迪", "长城汽车", "长安汽车", "赛力斯", "宇通客车", "拓普集团", "三花智控"),
        industry_chains=("新能源汽车", "汽车整车", "汽车零部件", "智能底盘"),
    ),
    ExportCommodityProfile(
        category="新能源与绿色制造",
        commodity="锂离子蓄电池（动力与储能锂电池）",
        trade_type="出口",
        keywords=("锂电池", "蓄电池", "储能电池", "动力电池", "锂电", "电池出口"),
        unit="亿个 / 亿美元",
        description="外贸“新三样”核心代表，海外工商业储能与欧洲动力电池装机需求旺盛",
        key_markets="欧洲、北美、东南亚、非洲",
        related_a_stocks=("宁德时代", "亿纬锂能", "国轩高科", "欣旺达", "派能科技"),
        industry_chains=("锂电池", "储能系统", "正极材料", "动力电池"),
    ),
    ExportCommodityProfile(
        category="新能源与绿色制造",
        commodity="太阳能电池（光伏组件与电池片）",
        trade_type="出口",
        keywords=("光伏", "太阳能电池", "光伏组件", "光伏逆变器", "电池片", "硅片"),
        unit="万个 / 亿美元",
        description="全球光伏产业链 80% 以上产能集中在中国，欧洲与新兴市场光伏装机拉动出口",
        key_markets="欧洲、巴西、印度、中东、东南亚",
        related_a_stocks=("晶科能源", "晶澳科技", "天合光能", "阳光电源", "锦浪科技"),
        industry_chains=("光伏组件", "逆变器", "多晶硅", "光伏支架"),
    ),
    ExportCommodityProfile(
        category="消费电子与半导体",
        commodity="集成电路（芯片与半导体器件）",
        trade_type="出口/进口双向",
        keywords=("集成电路", "芯片", "半导体", "ic", "晶圆", "存储芯片"),
        unit="亿个 / 亿美元",
        description="我国第一大进口单一商品类别（每年进口额超 3000 亿美元），同时成熟制程与封测出口快速提升",
        key_markets="进口源: 中国台湾、韩国、日本；出口地: 东南亚、中国香港",
        related_a_stocks=("中芯国际", "华虹公司", "长电科技", "通富微电", "北方华创", "兆易创新"),
        industry_chains=("半导体设计", "晶圆制造", "半导体封测", "国产替代"),
    ),
    ExportCommodityProfile(
        category="消费电子与半导体",
        commodity="手机与便携式自动数据处理设备",
        trade_type="出口",
        keywords=("手机", "智能手机", "电脑", "笔记本", "平板", "消费电子"),
        unit="万台 / 亿美元",
        description="传统机电出口主力，受全球消费电子换机周期与 AI 终端升级驱动",
        key_markets="北美、欧洲、东南亚、拉美",
        related_a_stocks=("立讯精密", "歌尔股份", "蓝思科技", "传音控股", "领益智造"),
        industry_chains=("消费电子", "苹果产业链", "安卓产业链", "光学模组"),
    ),
    ExportCommodityProfile(
        category="机械装备与高端制造",
        commodity="船舶与远洋工程装备",
        trade_type="出口",
        keywords=("船舶", "造船", "集装箱船", "lng船", "散货船", "油轮", "海工装备"),
        unit="艘 / 亿美元",
        description="全球造船三大指标全面领先，处于大周期上行与绿色双燃料替代红利期",
        key_markets="希腊、新加坡、日本、欧美航运公司",
        related_a_stocks=("中国船舶", "中船防务", "中国重工", "亚星锚链"),
        industry_chains=("造船工业", "航运物流", "船用柴油机", "特种钢材"),
    ),
    ExportCommodityProfile(
        category="机械装备与高端制造",
        commodity="工程机械（挖掘机、装载机与起重机）",
        trade_type="出口",
        keywords=("工程机械", "挖掘机", "装载机", "起重机", "叉车", "矿山机械"),
        unit="台 / 亿美元",
        description="国内地产筑底期，海外“一带一路”沿线与欧美矿山基建成为核心增长引擎",
        key_markets="东南亚、中东、拉美、非洲、俄罗斯",
        related_a_stocks=("三一重工", "徐工机械", "中联重科", "柳工", "恒立液压"),
        industry_chains=("工程机械", "液压件", "重型卡车", "矿山开采"),
    ),
    ExportCommodityProfile(
        category="白色家电与轻工",
        commodity="家用电器（空调、冰箱、洗衣机、液晶电视）",
        trade_type="出口",
        keywords=("家电", "空调", "冰箱", "洗衣机", "电视机", "小家电"),
        unit="万台 / 亿美元",
        description="全球家电制造中枢，自主品牌出海与海外代工并进，受海外补库与气候因素拉动",
        key_markets="北美、欧洲、东南亚、拉美",
        related_a_stocks=("美的集团", "海尔智家", "格力电器", "海信视像", "三花智控"),
        industry_chains=("白色家电", "黑色家电", "制冷配件", "小家电"),
    ),
    ExportCommodityProfile(
        category="大宗商品与战略原材料",
        commodity="钢材与未锻轧铝及铝材",
        trade_type="出口",
        keywords=("钢材", "铝材", "特钢", "不锈钢", "电解铝"),
        unit="万吨 / 亿美元",
        description="高性价比优势满足新兴市场基建与制造业需求，出口量处于高位",
        key_markets="东南亚、中东、拉美、非洲",
        related_a_stocks=("宝钢股份", "华菱钢铁", "中国铝业", "南山铝业"),
        industry_chains=("普钢", "特种钢铁", "铝合金加工", "基建工程"),
    ),
    ExportCommodityProfile(
        category="大宗商品与能源资源",
        commodity="原油、铁矿砂与天然气",
        trade_type="进口",
        keywords=("原油", "铁矿石", "铁矿砂", "天然气", "煤炭", "大宗进口"),
        unit="万吨 / 亿美元",
        description="我国基础能源与工业原材料主要进口依赖品，直接决定国内工业品输入性成本",
        key_markets="俄罗斯、沙特、澳大利亚、巴西、印尼",
        related_a_stocks=("中国海油", "中国石油", "宝钢股份", "河钢资源"),
        industry_chains=("石油炼化", "高炉炼铁", "火力发电", "港口物流"),
    ),
)


def _number(value: Any, *, divisor: int = 1) -> float | None:
    if value is None or isinstance(value, bool):
        return None
    try:
        number = float(value)
        return round(number / divisor, 2) if math.isfinite(number) else None
    except (ValueError, TypeError, OverflowError):
        return None


async def fetch_macro_customs_data() -> list[dict[str, Any]]:
    """从东方财富数据中心获取近 12 个月全国海关进出口月度总况。

    上游 EXIT_BASE/IMPORT_BASE 等金额字段单位为千美元，此处统一除以
    100000 换算为亿美元（与 macro/normalizer._normalize_trade 口径一致）；
    同比百分数字段不换算。
    """
    rows = []
    try:
        raw_rows = await provider_gateway.call_blocking(
            "eastmoney",
            "fetch_china_trade",
            get_provider("eastmoney").fetch_china_trade,
            semaphore=eastmoney_semaphore,
        )
        for row in raw_rows[:12]:
            # 逐行容错：单行脏数据只跳过该行，不丢掉剩余月份
            try:
                exit_val = _number(row.get("EXIT_BASE"), divisor=100000)
                import_val = _number(row.get("IMPORT_BASE"), divisor=100000)
                exit_yoy = _number(row.get("EXIT_BASE_SAME"))
                import_yoy = _number(row.get("IMPORT_BASE_SAME"))
                trade_balance = round(exit_val - import_val, 2) if exit_val is not None and import_val is not None else None
                if exit_val is None and import_val is None:
                    continue

                rows.append(
                    {
                        "month": row.get("TIME", ""),
                        "report_date": (row.get("REPORT_DATE") or "")[:10],
                        "export_val": exit_val,
                        "import_val": import_val,
                        "trade_balance": trade_balance,
                        "balance_status": "数据不足" if trade_balance is None else "贸易顺差" if trade_balance >= 0 else "贸易逆差",
                        "export_yoy_pct": exit_yoy,
                        "import_yoy_pct": import_yoy,
                        "export_accumulate": _number(row.get("EXIT_ACCUMULATE"), divisor=100000),
                        "import_accumulate": _number(row.get("IMPORT_ACCUMULATE"), divisor=100000),
                        "export_accumulate_yoy_pct": _number(row.get("EXIT_ACCUMULATE_SAME")),
                        "import_accumulate_yoy_pct": _number(row.get("IMPORT_ACCUMULATE_SAME")),
                    }
                )
            except (TypeError, ValueError) as row_err:
                logger.debug("海关数据脏行跳过: row=%s, error=%s", row, row_err)
    except Exception as exc:
        logger.warning("海关进出口月度数据获取失败: %s", exc)

    return rows


def _match_commodity_profiles(commodity_query: str) -> list[ExportCommodityProfile]:
    clean = commodity_query.strip().lower()
    if not clean or clean in ("all", "全部", "总览", "概览", "出海", "外贸"):
        return list(KEY_COMMODITY_PROFILES)

    matched = []
    for prof in KEY_COMMODITY_PROFILES:
        if (
            clean in prof.commodity.lower()
            or prof.commodity.lower() in clean
            or clean in prof.category.lower()
            or any(clean in kw or kw in clean for kw in prof.keywords)
            or any(clean in stock for stock in prof.related_a_stocks)
            or any(clean in chain for chain in prof.industry_chains)
        ):
            matched.append(prof)
    return matched


async def get_customs_trade_data(commodity: str = "") -> dict[str, Any]:
    """获取海关进出口月度总览与重点商品出海/进口数据看板。"""
    cache_key = f"customs_trade_v2_{commodity.strip().lower()}"
    cached = cache.get(cache_key)
    if cached is not None:
        return cast(dict[str, Any], cached)

    macro_rows = await fetch_macro_customs_data()
    latest_macro = macro_rows[0] if macro_rows else None
    matched_profiles = _match_commodity_profiles(commodity)

    profiles_output = [
        {
            "data_kind": "static_reference",
            "source": "builtin_reference",
            "category": prof.category,
            "commodity": prof.commodity,
            "trade_type": prof.trade_type,
            "unit": prof.unit,
            "description": prof.description,
            "key_target_markets": prof.key_markets,
            "related_a_stocks": list(prof.related_a_stocks),
            "industry_chains": list(prof.industry_chains),
        }
        for prof in matched_profiles
    ]

    response = {
        "data_scope": "national_macro",
        "source": "eastmoney_china_trade",
        "amount_unit": "USD_100_million",
        "macro_status": "unavailable" if not macro_rows else "available" if all(row.get("export_val") is not None and row.get("import_val") is not None for row in macro_rows) else "partial",
        "profile_match_status": "matched" if matched_profiles else "not_found",
        "commodity_series_available": False,
        "caveats": ["数值仅为全国进出口总量，不代表查询商品的数量、金额、均价或目的地。", "商品、目标市场、关联公司及投资逻辑为静态研究线索，未由当期海关数据验证。"],
        "query": commodity.strip() or "全国海关外贸与重点出海商品概览",
        "latest_month_summary": latest_macro,
        "recent_12m_macro_trend": macro_rows,
        "matched_commodity_profiles": profiles_output,
        "investment_implications": {
            "export_driver": "出口是拉动中国高端制造业（汽车、电池、光伏、工程机械、家电）产能消化的核心增量引擎。",
            "substitute_driver": "集成电路与高端装备等进口大类是国产替代自主可控（信创/半导体设备）的核心验证标尺。",
        },
    }

    if macro_rows and all(row.get("export_val") is not None and row.get("import_val") is not None for row in macro_rows):
        cache.set(cache_key, response, ttl=_CACHE_TTL_SECONDS)
    return response
