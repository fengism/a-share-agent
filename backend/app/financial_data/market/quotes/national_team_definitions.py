"""国家队监测的静态定义：ETF / 指数池、托底里程碑与机构画像。

这些常量人工维护、与采集和聚合无关，单独放一个文件后，增删成员只需看名单本身，
不必在两千行的采集逻辑里翻找。
"""

from __future__ import annotations

import logging
from dataclasses import dataclass
from typing import Literal

from app.financial_data.market.quotes.schemas import (
    NationalTeamCumData,
    NationalTeamHolderEntity,
    NationalTeamIndustryAllocation,
    NationalTeamIntradayItem,
    NationalTeamIntradayMinuteData,
    NationalTeamIntradayObservation,
    NationalTeamMilestone,
    NationalTeamPortrait,
    NationalTeamSupportVolumeData,
    NationalTeamSupportVolumeItem,
    NationalTeamTopHolding,
    NationalTeamTypicalCaseData,
)

#: 份额单位换算：1 亿份。
YI = 100_000_000
logger = logging.getLogger(__name__)
#: 指数聚合允许缺失部分成员，但覆盖不足一半时不生成点位，避免用极少数 ETF 冒充整条指数。
INDEX_MIN_COVERAGE = 0.5
METHOD = "按 ETF 逐只计算：份额变化 × 当日 ETF 收盘价，并在宽基层级汇总；份额单位为亿份，资金单位为亿元。"
DISCLAIMER = (
    "ETF 份额变化仅是观察国家队资金行为的代理指标，不等于中央汇金真实持仓；申购赎回可能来自其他机构或个人投资者。"
)

@dataclass(frozen=True, slots=True)
class EtfDefinition:
    code: str
    name: str
    fund_manager: str
    exchange: Literal["SH", "SZ"]
    index_key: str
    category: str = "core_broad"


@dataclass(frozen=True, slots=True)
class IndexDefinition:
    key: str
    name: str
    index_code: str
    category: str = "core_broad"


INDEX_POOL: dict[str, IndexDefinition] = {
    "csi300": IndexDefinition("csi300", "沪深300", "000300.SH", "core_broad"),
    "sz50": IndexDefinition("sz50", "上证50", "000016.SH", "core_broad"),
    "csi_a500": IndexDefinition("csi_a500", "中证A500", "000510.SH", "a500"),
    "csi500": IndexDefinition("csi500", "中证500", "000905.SH", "growth"),
    "csi1000": IndexDefinition("csi1000", "中证1000", "000852.SH", "growth"),
    "csi2000": IndexDefinition("csi2000", "中证2000", "399303.SZ", "growth"),
    "star50": IndexDefinition("star50", "科创50", "000688.SH", "growth"),
    "star100": IndexDefinition("star100", "科创100", "000698.SH", "growth"),
    "chinext": IndexDefinition("chinext", "创业板", "399006.SZ", "growth"),
    "dividend": IndexDefinition("dividend", "红利低波", "000015.SH", "dividend"),
}

ETF_POOL: dict[str, EtfDefinition] = {
    # 沪深300
    "510300": EtfDefinition("510300", "华泰柏瑞沪深300ETF", "华泰柏瑞基金", "SH", "csi300", "core_broad"),
    "510310": EtfDefinition("510310", "易方达沪深300ETF", "易方达基金", "SH", "csi300", "core_broad"),
    "510330": EtfDefinition("510330", "华夏沪深300ETF", "华夏基金", "SH", "csi300", "core_broad"),
    "159919": EtfDefinition("159919", "嘉实沪深300ETF", "嘉实基金", "SZ", "csi300", "core_broad"),
    # 上证50
    "510050": EtfDefinition("510050", "华夏上证50ETF", "华夏基金", "SH", "sz50", "core_broad"),
    # 中证A500
    "560510": EtfDefinition("560510", "国泰中证A500ETF", "国泰基金", "SH", "csi_a500", "a500"),
    "159338": EtfDefinition("159338", "景顺长城中证A500ETF", "景顺长城基金", "SZ", "csi_a500", "a500"),
    "512050": EtfDefinition("512050", "华泰柏瑞中证A500ETF", "华泰柏瑞基金", "SH", "csi_a500", "a500"),
    "159352": EtfDefinition("159352", "华夏中证A500ETF", "华夏基金", "SZ", "csi_a500", "a500"),
    # 中证500
    "510500": EtfDefinition("510500", "南方中证500ETF", "南方基金", "SH", "csi500", "growth"),
    # 中证1000
    "512100": EtfDefinition("512100", "南方中证1000ETF", "南方基金", "SH", "csi1000", "growth"),
    "159845": EtfDefinition("159845", "华夏中证1000ETF", "华夏基金", "SZ", "csi1000", "growth"),
    "560010": EtfDefinition("560010", "广发中证1000ETF", "广发基金", "SH", "csi1000", "growth"),
    "159629": EtfDefinition("159629", "富国中证1000ETF", "富国基金", "SZ", "csi1000", "growth"),
    # 中证2000
    "563000": EtfDefinition("563000", "华泰柏瑞中证2000ETF", "华泰柏瑞基金", "SH", "csi2000", "growth"),
    "159531": EtfDefinition("159531", "南方中证2000ETF", "南方基金", "SZ", "csi2000", "growth"),
    # 科创板与创业板
    "588080": EtfDefinition("588080", "易方达上证科创板50ETF", "易方达基金", "SH", "star50", "growth"),
    "588190": EtfDefinition("588190", "银华科创100ETF", "银华基金", "SH", "star100", "growth"),
    "159915": EtfDefinition("159915", "易方达创业板ETF", "易方达基金", "SZ", "chinext", "growth"),
    # 红利低波 / 央企红利
    "512890": EtfDefinition("512890", "华泰柏瑞红利低波ETF", "华泰柏瑞基金", "SH", "dividend", "dividend"),
    "510880": EtfDefinition("510880", "华泰柏瑞红利ETF", "华泰柏瑞基金", "SH", "dividend", "dividend"),
    "561580": EtfDefinition("561580", "华泰柏瑞央企红利ETF", "华泰柏瑞基金", "SH", "dividend", "dividend"),
}


NATIONAL_TEAM_MILESTONES: list[NationalTeamMilestone] = [
    NationalTeamMilestone(
        date="2023-10-23",
        title="汇金首次公告增持 ETF",
        type="statement",
        description="中央汇金宣布买入交易型开放式指数基金（ETF），并表示将在未来继续增持，打响本轮护盘第一枪。",
        index_points={"沪深300": 3474.75, "上证50": 2405.02},
    ),
    NationalTeamMilestone(
        date="2024-01-18",
        title="沪深300 ETF 尾盘天量扫货",
        type="intervention",
        description="易方达、华泰柏瑞、华夏、嘉实等 4 只核心沪深300 ETF 单日合计成交突破 310 亿元，尾盘强势逆转翻红。",
        index_points={"沪深300": 3274.73, "上证50": 2243.68},
    ),
    NationalTeamMilestone(
        date="2024-02-06",
        title="汇金扩大增持范围并加大力度",
        type="policy",
        description="中央汇金公告充分认可当前A股配置价值，扩大增持 ETF 范围，持续加大增持力度，坚决维护资本市场平稳运行。",
        index_points={"沪深300": 3316.33, "中证1000": 4272.71},
    ),
    NationalTeamMilestone(
        date="2024-04-12",
        title="新“国九条”发布与汇金千亿底仓",
        type="policy",
        description="国务院发布新“国九条”；基金一季报证实汇金一季度增持三大宽基 ETF 耗资超 1400 亿元，长线底仓夯实。",
        index_points={"沪深300": 3475.84, "上证50": 2406.88},
    ),
    NationalTeamMilestone(
        date="2024-09-24",
        title="国新办发布一揽子重磅金融政策",
        type="liquidity",
        description="央行宣布降准、降息，首创证券基金保险互换便利（SFISF 5000亿）与股票回购增持再贷款（3000亿），系统性制度化托底。",
        index_points={"沪深300": 3379.84, "上证50": 2420.50},
    ),
    NationalTeamMilestone(
        date="2024-10-18",
        title="互换便利（SFISF）首批正式落地",
        type="liquidity",
        description="央行正式创设并接受金融机构 SFISF 申报，首批申请额度已超 2000 亿元，国家队流动性托底工具常态化运行。",
        index_points={"沪深300": 3925.23, "创业板指": 2195.10},
    ),
]


DEFAULT_NATIONAL_TEAM_PORTRAIT = NationalTeamPortrait(
    reporting_period="2024年报 / 2024Q3权威公告",
    total_market_value_trillion=3.85,
    as_of="2024-12-31",
    source="上市公司定期报告与公开公告（静态整理，非实时数据）",
    is_static=True,
    entities=[
        NationalTeamHolderEntity(
            name="中央汇金投资有限责任公司 / 汇金资管",
            short_name="中央汇金",
            role="国家级金融投资平台（平准与长效战略持股）",
            estimated_aum_trillion=2.45,
            focus="四大国有行、龙头券商及核心宽基 ETF",
        ),
        NationalTeamHolderEntity(
            name="中国证券金融股份有限公司",
            short_name="中证金 (CSF)",
            role="维稳流动性救市主力机构",
            estimated_aum_trillion=0.65,
            focus="大盘蓝筹、系统重要性券商及周期龙头",
        ),
        NationalTeamHolderEntity(
            name="全国社会保障基金理事会",
            short_name="全国社保基金",
            role="长期战略价值投资标杆",
            estimated_aum_trillion=0.75,
            focus="高股息红利、高端制造、医药生物与科技自主可控",
        ),
    ],
    industry_allocations=[
        NationalTeamIndustryAllocation(
            industry="银行金融",
            weight_pct=48.5,
            market_value_100m=18670.0,
            representative_stocks=["工商银行", "建设银行", "中国银行", "农业银行"],
        ),
        NationalTeamIndustryAllocation(
            industry="能源周期",
            weight_pct=16.2,
            market_value_100m=6237.0,
            representative_stocks=["中国神华", "中国石油", "中国石化", "陕西煤业"],
        ),
        NationalTeamIndustryAllocation(
            industry="高端制造与军工",
            weight_pct=11.5,
            market_value_100m=4428.0,
            representative_stocks=["中航沈飞", "中航光电", "三一重工"],
        ),
        NationalTeamIndustryAllocation(
            industry="消费与医药",
            weight_pct=9.8,
            market_value_100m=3773.0,
            representative_stocks=["贵州茅台", "伊利股份", "恒瑞医药"],
        ),
        NationalTeamIndustryAllocation(
            industry="科技与半导体",
            weight_pct=8.0,
            market_value_100m=3080.0,
            representative_stocks=["中芯国际", "海康威视", "中微公司"],
        ),
        NationalTeamIndustryAllocation(
            industry="公用事业与交运",
            weight_pct=6.0,
            market_value_100m=2310.0,
            representative_stocks=["长江电力", "京沪高铁", "大秦铁路"],
        ),
    ],
    top_holdings=[
        NationalTeamTopHolding(
            code="601398",
            name="工商银行",
            holder_name="中央汇金",
            shareholding_ratio_pct=34.79,
            market_value_100m=7850.0,
            industry="银行金融",
        ),
        NationalTeamTopHolding(
            code="601939",
            name="建设银行",
            holder_name="中央汇金",
            shareholding_ratio_pct=57.31,
            market_value_100m=6520.0,
            industry="银行金融",
        ),
        NationalTeamTopHolding(
            code="601288",
            name="农业银行",
            holder_name="中央汇金",
            shareholding_ratio_pct=40.03,
            market_value_100m=5930.0,
            industry="银行金融",
        ),
        NationalTeamTopHolding(
            code="601988",
            name="中国银行",
            holder_name="中央汇金",
            shareholding_ratio_pct=64.02,
            market_value_100m=5120.0,
            industry="银行金融",
        ),
        NationalTeamTopHolding(
            code="600900",
            name="长江电力",
            holder_name="证金/社保",
            shareholding_ratio_pct=4.85,
            market_value_100m=352.0,
            industry="公用事业",
        ),
        NationalTeamTopHolding(
            code="601857",
            name="中国石油",
            holder_name="中证金",
            shareholding_ratio_pct=0.62,
            market_value_100m=98.5,
            industry="能源周期",
        ),
        NationalTeamTopHolding(
            code="601088",
            name="中国神华",
            holder_name="证金/社保",
            shareholding_ratio_pct=2.15,
            market_value_100m=165.0,
            industry="能源周期",
        ),
        NationalTeamTopHolding(
            code="600519",
            name="贵州茅台",
            holder_name="证金/汇金",
            shareholding_ratio_pct=1.12,
            market_value_100m=215.0,
            industry="食品饮料",
        ),
        NationalTeamTopHolding(
            code="600036",
            name="招商银行",
            holder_name="中证金",
            shareholding_ratio_pct=2.98,
            market_value_100m=285.0,
            industry="银行金融",
        ),
        NationalTeamTopHolding(
            code="000063",
            name="中兴通讯",
            holder_name="全国社保基金",
            shareholding_ratio_pct=1.85,
            market_value_100m=29.8,
            industry="科技通信",
        ),
    ],
)


def load_default_intraday_observation() -> NationalTeamIntradayObservation:
    """加载重点 ETF 资金看板实盘分钟观测、累计线、放量案例与百亿放量信号对照基准。"""
    import json
    from pathlib import Path

    json_path = Path(__file__).parent / "national_team_intraday_data.json"
    if not json_path.exists():
        return NationalTeamIntradayObservation()

    try:
        with open(json_path, encoding="utf-8") as f:
            raw = json.load(f)
    except Exception as exc:
        logger.warning("加载国家队日内分钟观测数据失败: %s", exc)
        return NationalTeamIntradayObservation()

    init_d = raw.get("initData", {})
    cmp_d = raw.get("cmpData", {})
    typ_d = raw.get("typData", {})
    cum_d = raw.get("cumData", {})

    # 1. 分钟级走势与单只 ETF 表格
    minute_table = [
        NationalTeamIntradayItem(
            code=item.get("code", ""),
            name=item.get("name", ""),
            price=float(item.get("price", 0.0)),
            pct=float(item.get("pct", 0.0)),
            amount=float(item.get("amount", 0.0)),
        )
        for item in init_d.get("table", [])
    ]
    minute_data = NationalTeamIntradayMinuteData(
        pre_close=float(init_d.get("preClose", 0.0)),
        date=str(init_d.get("date", "")),
        times=list(init_d.get("times", [])),
        bars=[float(x) for x in init_d.get("bars", [])],
        closes=[float(x) for x in init_d.get("closes", [])],
        table=minute_table,
        built_at="2026-11-05 09:45",
    )

    # 2. 分钟累计成交额（今日 vs 昨日 vs 近20日均值）
    cum_data = NationalTeamCumData(
        slots=list(cum_d.get("slots", [])),
        prev_date=str(cum_d.get("prevDate", "")),
        prev=[float(x) for x in cum_d.get("prev", [])],
        avg_days=int(cum_d.get("avgDays", 20)),
        avg_from=str(cum_d.get("avgFrom", "")),
        avg_to=str(cum_d.get("avgTo", "")),
        avg20=[float(x) for x in cum_d.get("avg20", [])],
        built_at=str(cum_d.get("builtAt", "")),
    )

    # 3. 放量案例日 vs 常态交易日典型分钟特征
    typical_cases = NationalTeamTypicalCaseData(
        slots=list(typ_d.get("slots", [])),
        sup_amt=[float(x) for x in typ_d.get("supAmt", [])],
        sup_cum=[float(x) for x in typ_d.get("supCum", [])],
        nor_amt=[float(x) for x in typ_d.get("norAmt", [])],
        nor_cum=[float(x) for x in typ_d.get("norCum", [])],
        sup_n=int(typ_d.get("supN", 0)),
        nor_n=int(typ_d.get("norN", 0)),
        range=str(typ_d.get("range", "")),
    )

    # 4. 放量护盘日标定（单日净申购 > 100 亿）对比
    support_items = [
        NationalTeamSupportVolumeItem(
            date=item.get("date", ""),
            amount=float(item.get("amount", 0.0)),
            netflow=float(item["netflow"]) if item.get("netflow") is not None else None,
            is_support_day=True,
            is_pending=False,
        )
        for item in cmp_d.get("support", [])
    ]
    recent_items = [
        NationalTeamSupportVolumeItem(
            date=item.get("date", ""),
            amount=float(item.get("amount", 0.0)),
            netflow=float(item["netflow"]) if item.get("netflow") is not None else None,
            is_support_day=False,
            is_pending=bool(item.get("pending", False)),
        )
        for item in cmp_d.get("recent", [])
    ]
    volume_signals = NationalTeamSupportVolumeData(
        support_threshold_100m=100.0,
        support_days=support_items,
        recent_days=recent_items,
    )

    return NationalTeamIntradayObservation(
        minute=minute_data,
        cum=cum_data,
        typical_cases=typical_cases,
        volume_signals=volume_signals,
    )


DEFAULT_NATIONAL_TEAM_INTRADAY = load_default_intraday_observation()

