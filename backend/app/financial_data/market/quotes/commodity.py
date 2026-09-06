"""大宗商品与重要工业品现货/期货行情服务。"""

from __future__ import annotations

import logging
from dataclasses import dataclass
from typing import Any

import httpx

from app.core.cache import market_cache as cache

logger = logging.getLogger(__name__)

_CACHE_TTL_SECONDS = 30


@dataclass(frozen=True)
class CommodityItemSpec:
    symbol: str
    name: str
    sina_code: str
    category: str
    unit: str
    keywords: tuple[str, ...]
    description: str
    related_chains: tuple[str, ...]


COMMODITY_SPECS: tuple[CommodityItemSpec, ...] = (
    CommodityItemSpec(
        symbol="碳酸锂",
        name="碳酸锂连续",
        sina_code="nf_LC0",
        category="新能源金属",
        unit="元/吨",
        keywords=("碳酸锂", "锂", "电池级碳酸锂", "工业级碳酸锂", "lc", "正极材料", "锂电"),
        description="锂电池核心原材料，直接影响动力与储能电池电芯成本",
        related_chains=("锂电池", "新能源汽车", "储能", "正极材料", "动力电池"),
    ),
    CommodityItemSpec(
        symbol="工业硅",
        name="工业硅连续",
        sina_code="nf_SI0",
        category="新能源材料",
        unit="元/吨",
        keywords=("工业硅", "多晶硅", "金属硅", "有机硅", "si", "光伏硅料", "硅片"),
        description="多晶硅与有机硅上游基础原料，光伏与半导体产业关键上游",
        related_chains=("光伏", "多晶硅", "半导体", "有机硅", "光伏组件"),
    ),
    CommodityItemSpec(
        symbol="沪铜",
        name="电解铜连续",
        sina_code="nf_CU0",
        category="有色金属",
        unit="元/吨",
        keywords=("铜", "沪铜", "电解铜", "阴极铜", "cu", "铜线", "铜箔"),
        description="宏观经济晴雨表（铜博士），电力电网、新能源车与电子PCB核心导电材料",
        related_chains=("电网设备", "消费电子", "PCB", "新能源汽车", "特种电缆"),
    ),
    CommodityItemSpec(
        symbol="沪铝",
        name="电解铝连续",
        sina_code="nf_AL0",
        category="有色金属",
        unit="元/吨",
        keywords=("铝", "沪铝", "电解铝", "原铝", "al", "铝材", "铝合金"),
        description="高耗能大宗金属，广泛用于汽车轻量化、光伏边框及建筑结构",
        related_chains=("汽车轻量化", "光伏支架", "特高压", "航空航天"),
    ),
    CommodityItemSpec(
        symbol="沪锌",
        name="沪锌连续",
        sina_code="nf_ZN0",
        category="有色金属",
        unit="元/吨",
        keywords=("锌", "沪锌", "电解锌", "zn", "镀锌"),
        description="防腐镀锌板核心原料，与基建和汽车制造密切相关",
        related_chains=("镀锌板", "钢结构", "汽车制造", "压铸合金"),
    ),
    CommodityItemSpec(
        symbol="沪镍",
        name="沪镍连续",
        sina_code="nf_NI0",
        category="有色金属",
        unit="元/吨",
        keywords=("镍", "沪镍", "电解镍", "ni", "高镍", "三元前驱体"),
        description="不锈钢制造与高镍三元动力电池关键材料",
        related_chains=("不锈钢", "三元动力电池", "高温合金", "特钢"),
    ),
    CommodityItemSpec(
        symbol="沪锡",
        name="沪锡连续",
        sina_code="nf_SN0",
        category="有色金属",
        unit="元/吨",
        keywords=("锡", "沪锡", "精锡", "sn", "焊锡", "锡膏"),
        description="电子芯片封装与焊接必须材料，半导体景气度关键先行指标",
        related_chains=("半导体封装", "消费电子", "光伏焊带", "汽车电子"),
    ),
    CommodityItemSpec(
        symbol="黄金",
        name="沪金连续",
        sina_code="nf_AU0",
        category="贵金属",
        unit="元/克",
        keywords=("黄金", "沪金", "金价", "au", "金条", "首饰金"),
        description="全球核心避险资产与抗通胀信用锚",
        related_chains=("黄金采选", "珠宝首饰", "央行储备", "贵金属贸易"),
    ),
    CommodityItemSpec(
        symbol="白银",
        name="沪银连续",
        sina_code="nf_AG0",
        category="贵金属",
        unit="元/千克",
        keywords=("白银", "沪银", "银价", "ag", "银浆", "光伏银浆"),
        description="兼具金融属性与工业属性，光伏正面导电银浆核心原料",
        related_chains=("光伏银浆", "电子元器件", "珠宝", "医疗感光"),
    ),
    CommodityItemSpec(
        symbol="螺纹钢",
        name="螺纹钢连续",
        sina_code="nf_RB0",
        category="黑色建材",
        unit="元/吨",
        keywords=("螺纹钢", "建材", "钢材", "rb", "钢筋"),
        description="建筑与基建主要钢材，反映国内房地产与基建投资开工强度",
        related_chains=("房地产", "基建工程", "特种钢铁", "机械制造"),
    ),
    CommodityItemSpec(
        symbol="热卷",
        name="热轧卷板连续",
        sina_code="nf_HC0",
        category="黑色建材",
        unit="元/吨",
        keywords=("热卷", "热轧板", "板材", "hc", "汽车板"),
        description="制造业板材基石，广泛用于汽车、家电、集装箱与船舶",
        related_chains=("汽车制造", "白色家电", "集装箱", "造船工业"),
    ),
    CommodityItemSpec(
        symbol="铁矿石",
        name="铁矿石连续",
        sina_code="nf_I0",
        category="黑色建材",
        unit="元/吨",
        keywords=("铁矿石", "铁矿", "普氏", "i", "精粉"),
        description="钢铁高炉冶炼第一大原料，成本占粗钢生产 50% 以上",
        related_chains=("钢铁冶炼", "港口航运", "采掘业", "高炉炼铁"),
    ),
    CommodityItemSpec(
        symbol="焦炭",
        name="焦炭连续",
        sina_code="nf_J0",
        category="黑色建材",
        unit="元/吨",
        keywords=("焦炭", "冶金焦", "j", "焦化"),
        description="炼铁高炉发热剂与还原剂，直接决定钢厂入炉成本",
        related_chains=("焦化", "钢铁", "煤化工", "高炉炼铁"),
    ),
    CommodityItemSpec(
        symbol="玻璃",
        name="玻璃连续",
        sina_code="nf_FG0",
        category="黑色建材",
        unit="元/吨",
        keywords=("玻璃", "浮法玻璃", "平板玻璃", "fg", "光伏玻璃"),
        description="建筑门窗竣工与光伏组件封装的关键基材",
        related_chains=("建筑装饰", "光伏组件", "汽车玻璃", "纯碱"),
    ),
    CommodityItemSpec(
        symbol="原油",
        name="SC原油连续",
        sina_code="nf_SC0",
        category="能源化工",
        unit="元/桶",
        keywords=("原油", "石油", "sc", "布伦特", "wti", "成品油"),
        description="大宗商品之王，石化全产业链核心成本源头与全球通胀风向标",
        related_chains=("石油化工", "炼化一体化", "成品油", "交通运输"),
    ),
    CommodityItemSpec(
        symbol="甲醇",
        name="甲醇连续",
        sina_code="nf_MA0",
        category="能源化工",
        unit="元/吨",
        keywords=("甲醇", "ma", "mto", "煤制甲醇", "天然气制甲醇"),
        description="煤化工核心中间品，用于制烯烃 (MTO)、甲醛与醋酸",
        related_chains=("煤化工", "烯烃", "精细化工", "新能源甲醇燃料"),
    ),
    CommodityItemSpec(
        symbol="PTA",
        name="精对苯二甲酸连续",
        sina_code="nf_TA0",
        category="能源化工",
        unit="元/吨",
        keywords=("pta", "精对苯二甲酸", "ta", "聚酯", "化纤"),
        description="涤纶化纤与聚酯瓶片核心原料，连接石化与纺织服装",
        related_chains=("聚酯化纤", "纺织服装", "瓶级PET", "芳烃一体化"),
    ),
    CommodityItemSpec(
        symbol="纯碱",
        name="纯碱连续",
        sina_code="nf_SA0",
        category="能源化工",
        unit="元/吨",
        keywords=("纯碱", "碳酸钠", "sa", "轻碱", "重碱"),
        description="玻璃工业核心配料，同时用于锂电碳酸锂加工与洗涤剂",
        related_chains=("浮法玻璃", "光伏玻璃", "碳酸锂提纯", "精细化学品"),
    ),
    CommodityItemSpec(
        symbol="生猪",
        name="生猪连续",
        sina_code="nf_LH0",
        category="农产品养殖",
        unit="元/吨",
        keywords=("生猪", "猪肉", "lh", "外三元", "仔猪", "猪周期"),
        description="农业养殖核心品种，猪粮比与养殖盈利周期关键标尺",
        related_chains=("生猪养殖", "饲料加工", "屠宰肉类", "动保疫苗"),
    ),
    CommodityItemSpec(
        symbol="豆粕",
        name="豆粕连续",
        sina_code="nf_M0",
        category="农产品养殖",
        unit="元/吨",
        keywords=("豆粕", "m", "大豆压榨", "蛋白饲料"),
        description="畜禽养殖核心蛋白原料，饲料配方中占比最大的蛋白源",
        related_chains=("饲料工业", "大豆压榨", "生猪养殖", "家禽养殖"),
    ),
    CommodityItemSpec(
        symbol="玉米",
        name="玉米连续",
        sina_code="nf_C0",
        category="农产品养殖",
        unit="元/吨",
        keywords=("玉米", "c", "饲料能量", "玉米淀粉"),
        description="养殖饲料能量来源第一大粮食品种，决定猪料禽料成本",
        related_chains=("农业种植", "饲料能量源", "深加工淀粉", "燃料乙醇"),
    ),
    CommodityItemSpec(
        symbol="白糖",
        name="白糖连续",
        sina_code="nf_SR0",
        category="农产品养殖",
        unit="元/吨",
        keywords=("白糖", "食糖", "sr", "甘蔗糖", "甜菜糖"),
        description="食品工业与饮料制造基础原料",
        related_chains=("制糖工业", "软饮料", "烘焙食品", "调味品"),
    ),
)


def _match_commodity_specs(query: str) -> list[CommodityItemSpec]:
    clean_query = query.strip().lower()
    if not clean_query or clean_query in ("all", "overview", "全部", "大宗商品", "大盘", "概览"):
        return list(COMMODITY_SPECS)

    matched = []
    for spec in COMMODITY_SPECS:
        if (
            clean_query in spec.symbol.lower()
            or spec.symbol.lower() in clean_query
            or clean_query in spec.name.lower()
            or clean_query in spec.category.lower()
            or any(clean_query in kw or kw in clean_query for kw in spec.keywords)
            or any(clean_query in chain for chain in spec.related_chains)
        ):
            matched.append(spec)
    return matched or list(COMMODITY_SPECS)


def _parse_sina_futures_line(line: str) -> tuple[str, dict[str, Any]] | None:
    """解析单条新浪 nf_ 合约行情行，返回 (sina_code, quote)。

    上游字段布局经 akshare futures_zh_spot 列映射与 2026-09 实测双重核对：
    2 开盘 / 3 最高 / 4 最低 / 5 昨收 / 6 买价 / 8 最新价 / 10 昨结算 /
    13 持仓量 / 14 成交量 / 17 行情日期。
    """
    if "=" not in line or '"' not in line:
        return None
    code_part = line.split("=")[0].split("_")[-1]
    fields = line.split('"')[1].split(",")
    if len(fields) < 18:
        return None
    try:
        open_price = float(fields[2])
        high_price = float(fields[3])
        low_price = float(fields[4])
        # 涨跌幅官方口径基于昨结算价，优先取 fields[10]；昨收(fields[5])仅兜底
        prev_settle = float(fields[10]) if float(fields[10]) > 0 else float(fields[5])
        current_price = float(fields[8]) if float(fields[8]) > 0 else float(fields[6])
        if current_price > 0 and prev_settle > 0:
            change = current_price - prev_settle
            change_pct = change / prev_settle * 100
        else:
            # 非交易时段最新价与买价可能均为 0，输出 None 而不是 0/-100%
            change = None
            change_pct = None
        open_interest = float(fields[13])
        volume = float(fields[14])
        quote_date = fields[17]
    except (ValueError, IndexError):
        return None
    return f"nf_{code_part}", {
        "price": round(current_price, 2) if current_price > 0 else None,
        "prev_settle": round(prev_settle, 2) if prev_settle > 0 else None,
        "change": round(change, 2) if change is not None else None,
        "change_pct": round(change_pct, 2) if change_pct is not None else None,
        "open": round(open_price, 2),
        "high": round(high_price, 2),
        "low": round(low_price, 2),
        "volume": int(volume),
        "open_interest": int(open_interest),
        "date": quote_date,
    }


async def fetch_commodity_quotes(specs: list[CommodityItemSpec]) -> list[dict[str, Any]]:
    """批量从新浪行情通道获取大宗商品/工业品现货主力实时价格。"""
    if not specs:
        return []

    symbols_param = ",".join(spec.sina_code for spec in specs)
    url = f"https://hq.sinajs.cn/list={symbols_param}"
    headers = {
        "Referer": "https://finance.sina.com.cn",
        "User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7)",
    }

    quote_map: dict[str, dict[str, Any]] = {}
    try:
        async with httpx.AsyncClient(timeout=6.0) as client:
            resp = await client.get(url, headers=headers)
            for line in resp.text.strip().split("\n"):
                parsed = _parse_sina_futures_line(line)
                if parsed is not None:
                    quote_map[parsed[0]] = parsed[1]
    except Exception as exc:
        logger.warning("大宗商品行情获取失败: %s", exc)

    results = []
    for spec in specs:
        quote = quote_map.get(spec.sina_code, {})
        results.append({
            "symbol": spec.symbol,
            "name": spec.name,
            "contract": spec.sina_code.replace("nf_", ""),
            "category": spec.category,
            "unit": spec.unit,
            "latest_price": quote.get("price"),
            "change": quote.get("change"),
            "change_pct": quote.get("change_pct"),
            "high": quote.get("high"),
            "low": quote.get("low"),
            "open": quote.get("open"),
            "prev_settle": quote.get("prev_settle"),
            "volume": quote.get("volume"),
            "open_interest": quote.get("open_interest"),
            "date": quote.get("date"),
            "description": spec.description,
            "related_chains": list(spec.related_chains),
        })
    return results


async def get_commodity_spot_prices(symbol: str = "") -> dict[str, Any]:
    """查询大宗商品与重要工业品现货/主力合约最新价格与产业链映射。"""
    cache_key = f"commodity_spot_{symbol.strip().lower()}"
    cached = cache.get(cache_key)
    if cached is not None:
        return cached

    matched_specs = _match_commodity_specs(symbol)
    items = await fetch_commodity_quotes(matched_specs)

    response = {
        "query": symbol.strip() or "全部重要大宗商品",
        "total_count": len(items),
        "items": items,
    }
    cache.set(cache_key, response, ttl=_CACHE_TTL_SECONDS)
    return response
