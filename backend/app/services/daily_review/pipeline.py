import asyncio
import json
import logging

from datetime import datetime

from app.config import get_settings
from app.models.daily_review import DailyReviewDataSnapshot, DailyReviewRequest, DailyReviewResult, DailyReviewSection
from app.services.daily_review.storage import load_daily_review, save_daily_review
from app.services.daily_review.formatter import normalize_llm_review
from app.services.llm.client import create_llm_client
from app.services.daily_review.prompts import MARKET_SYSTEM_PROMPT, MARKET_USER_PROMPT
from app.services.market import get_indices
from app.services.market.statistic import get_market_statistics
from app.services.market.dragon_tiger import get_dragon_tiger_list
from app.services.market.hot_rank import get_hot_stocks, get_ths_hot_concept, get_ths_hot_industry
from app.services.market.news import get_market_news
from app.services.market.volume import get_realtime_market_volume
from app.services.market.macro import get_macro_data

logger = logging.getLogger(__name__)

def _build_fallback_review(date: str, snapshot: DailyReviewDataSnapshot) -> DailyReviewResult:
    """在 LLM 不可用时，根据数据快照构建一份纯模板化的复盘报告。

    Param:
        date: 复盘日期
        snapshot: 当日市场数据快照
    Return:
        基础复盘结果对象
    """
    index_bullets = [
        f"{item.get('name', '')}：{item.get('price', '-')}, 涨跌幅 {item.get('change_pct', '-') }%"
        for item in snapshot.indices[:6]
        if item.get("name")
    ]
    market_statistics = snapshot.market_statistics or {}
    hot_concept_bullets = [
        f"{item.get('name', '')}：热度 {item.get('hot_value', '-')}, 涨跌幅 {item.get('change_pct', '-') }%"
        for item in snapshot.hot_concepts[:5]
        if item.get("name")
    ]
    sector_bullets = [
        f"{item.get('name', '')}：涨跌幅 {item.get('change_pct', '-') }%，领涨股 {item.get('leading_stock', '-') }"
        for item in market_statistics.get("top_sectors", [])[:5]
        if item.get("name")
    ]
    dragon_bullets = [
        f"{item.get('name', '')}：净额 {item.get('net_amount', '-') }万，原因 {item.get('reason', '-') }"
        for item in snapshot.dragon_tiger[:5]
        if item.get("name")
    ]
    title = f"{date} 每日复盘"
    rising_indices = [item for item in snapshot.indices if isinstance(item.get("change_pct"), (int, float)) and item.get("change_pct", 0) > 0]
    weak_indices = [item for item in snapshot.indices if isinstance(item.get("change_pct"), (int, float)) and item.get("change_pct", 0) < 0]
    market_summary = (
        f"当日共整理 {len(snapshot.indices)} 个核心指数，其中上涨 {len(rising_indices)} 个、下跌 {len(weak_indices)} 个；"
        f"全市场上涨 {market_statistics.get('up_count', 0)} 家、下跌 {market_statistics.get('down_count', 0)} 家、平盘 {market_statistics.get('flat_count', 0)} 家；"
        f"涨停 {market_statistics.get('limit_up_count', 0)} 家、跌停 {market_statistics.get('limit_down_count', 0)} 家。"
    )
    return DailyReviewResult(
        date=date,
        title=title,
        generated_at=datetime.now().isoformat(),
        market_summary=market_summary,
        index_review=DailyReviewSection(title="指数表现", summary="主要指数涨跌与量价概览如下。", bullets=index_bullets),
        hotspot_review=DailyReviewSection(
            title="热点题材",
            summary="优先根据板块涨跌榜识别强势主线，再辅以热点概念热度。",
            bullets=sector_bullets or hot_concept_bullets,
        ),
        dragon_tiger_review=DailyReviewSection(
            title="龙虎榜",
            summary="选取当日活跃席位个股，观察资金偏好。",
            bullets=dragon_bullets,
        ),
        risk_alerts=[
            "若跌停家数抬升且下跌家数明显多于上涨家数，需警惕情绪退潮。"
            if market_statistics.get("down_count", 0) > market_statistics.get("up_count", 0)
            else "若强势板块集中且龙虎榜净买入不持续，需防范次日冲高回落。"
        ],
        opportunities=[
            "优先关注指数相对强势背景下，涨幅居前且有龙头股带动的板块。"
            if market_statistics.get("up_count", 0) >= market_statistics.get("down_count", 0)
            else "若指数分化但板块龙头延续，可关注局部主线的低吸机会。"
        ],
        strategy_notes=[
            f"先判断指数强弱，再看板块扩散，最后结合龙虎榜确认资金方向；当前涨停/跌停为 {market_statistics.get('limit_up_count', 0)}/{market_statistics.get('limit_down_count', 0)}。"
        ],
        data_snapshot=snapshot,
    )


def _build_prompt(date: str, snapshot: DailyReviewDataSnapshot) -> str:
    """根据数据快照构造发送给 LLM 的复盘 prompt 文本。

    Param:
        date: 复盘日期
        snapshot: 当日市场数据快照
    Return:
        格式化后的用户 prompt 字符串
    """
    market_statistics = snapshot.market_statistics or {}
    # 构建市场概览总结
    rising_indices = [item for item in snapshot.indices if isinstance(item.get("change_pct"), (int, float)) and item.get("change_pct", 0) > 0]
    weak_indices = [item for item in snapshot.indices if isinstance(item.get("change_pct"), (int, float)) and item.get("change_pct", 0) < 0]
    market_summary_placeholder = (
        f"当日整理 {len(snapshot.indices)} 个核心指数，其中上涨 {len(rising_indices)} 个、下跌 {len(weak_indices)} 个；"
        f"全市场上涨 {market_statistics.get('up_count', 0)} 家、下跌 {market_statistics.get('down_count', 0)} 家、平盘 {market_statistics.get('flat_count', 0)} 家；"
        f"涨停 {market_statistics.get('limit_up_count', 0)} 家、跌停 {market_statistics.get('limit_down_count', 0)} 家。"
    )
    # 热门股票
    hot_stock_bullets = [
        f"{item.get('name', '')}： 涨跌幅 {item.get('change_pct', '-') }%，概念 {item.get('concept_tag', '-') }, 上榜原因 {item.get('pop_tag', '-') }"
        for item in snapshot.hot_stocks[:5]
        if item.get("name")
    ]
    
    # 构建市场成交额总结
    market_volume_placeholder_str = ""
    market_volume_labels = {
        "amount": "成交量",
        "amount_before_one_day": "昨日成交量",
        "amount_average_60_day": "60日成交量平均值",
    }
    for key, label in market_volume_labels.items():
        value = snapshot.market_volume.get(key)
        if value is None:
            continue
        value = value / 100000000.0 if isinstance(value, (int, float)) else value
        value_str = f"{value:.2f}" if isinstance(value, (int, float)) else str(value)
        market_volume_placeholder_str += f"{label}: {value_str}亿 "

    # 构建行业数据
    hot_concept_bullets = [
        f"{item.get('name', '')}：热度 {item.get('hot_value', '-')}, 涨跌幅 {item.get('change_pct', '-') }%"
        for item in snapshot.hot_concepts[:5]
        if item.get("name")
    ]
    top_sector_bullets = [
        f"{item.get('name', '')}：涨跌幅 {item.get('change_pct', '-') }%，领涨股 {item.get('leading_stock', '-') }"
        for item in snapshot.top_sectors[:5]
        if item.get("name")
    ]
    bottom_sector_bullets = [
        f"{item.get('name', '')}：涨跌幅 {item.get('change_pct', '-') }%，领跌股 {item.get('leading_stock', '-') }"
        for item in snapshot.bottom_sectors[:5]
        if item.get("name")
    ]
    dragon_bullets = [
        f"{item.get('name', '')}：净额 {item.get('net_amount', '-') }万，原因 {item.get('reason', '-') }"
        for item in snapshot.dragon_tiger[:5]
        if item.get("name")
    ]
    
    # 热门行业
    hot_industry_bullets = [
        f"{item.get('name', '')}：热度 {item.get('hot_value', '-')}, 涨跌幅 {item.get('change_pct', '-') }%"
        for item in snapshot.hot_industries[:5]
        if item.get("name")
    ]
    
    # 构建新闻数据
    news_bullets = [
        f"{item.get('title', '')}：{item.get('content', '-') }"
        for item in snapshot.market_news[:20]
        if item.get("title")
    ]

    # 构建宏观经济数据
    macro_bullets = []
    macro = snapshot.macro_data or {}
    cpi_latest = macro.get("cpi", {}).get("latest")
    if cpi_latest:
        macro_bullets.append(
            f"CPI({cpi_latest.get('TIME', '')}): 同比 {cpi_latest.get('NATIONAL_SAME', '-')}%, "
            f"环比 {cpi_latest.get('NATIONAL_SEQUENTIAL', '-')}%, 累计 {cpi_latest.get('NATIONAL_ACCUMULATE', '-')}%"
        )
    ppi_latest = macro.get("ppi", {}).get("latest")
    if ppi_latest:
        macro_bullets.append(
            f"PPI({ppi_latest.get('TIME', '')}): 当月 {ppi_latest.get('BASE', '-')}, "
            f"同比 {ppi_latest.get('BASE_SAME', '-')}%"
        )
    pmi_latest = macro.get("pmi", {}).get("latest")
    if pmi_latest:
        macro_bullets.append(
            f"PMI({pmi_latest.get('TIME', '')}): 制造业 {pmi_latest.get('MAKE_INDEX', '-')} "
            f"(同比 {pmi_latest.get('MAKE_SAME', '-')}%), "
            f"非制造业 {pmi_latest.get('NMAKE_INDEX', '-')} "
            f"(同比 {pmi_latest.get('NMAKE_SAME', '-')}%)"
        )
    money_latest = macro.get("money_supply", {}).get("latest")
    if money_latest:
        macro_bullets.append(
            f"货币供应({money_latest.get('TIME', '')}): "
            f"M2 {money_latest.get('BASIC_CURRENCY', '-')}亿 (同比 {money_latest.get('BASIC_CURRENCY_SAME', '-')}%), "
            f"M1 {money_latest.get('CURRENCY', '-')}亿 (同比 {money_latest.get('CURRENCY_SAME', '-')}%), "
            f"M0 {money_latest.get('FREE_CASH', '-')}亿 (同比 {money_latest.get('FREE_CASH_SAME', '-')}%)"
        )

    return MARKET_USER_PROMPT.format(
        date=date,
        indices_placeholder=json.dumps(snapshot.indices[:6], ensure_ascii=False),
        market_statistics_placeholder=market_summary_placeholder or json.dumps(snapshot.market_statistics, ensure_ascii=False),
        dragon_tiger_placeholder=dragon_bullets or json.dumps(snapshot.dragon_tiger[:20], ensure_ascii=False),
        hot_stocks_placeholder=hot_stock_bullets or json.dumps(snapshot.hot_stocks[:20], ensure_ascii=False),
        hot_concepts_placeholder=hot_concept_bullets or json.dumps(snapshot.hot_concepts[:5], ensure_ascii=False),
        hot_industries_placeholder=hot_industry_bullets or json.dumps(snapshot.hot_industries[:15], ensure_ascii=False),
        news_placeholder=news_bullets or json.dumps(snapshot.market_news[:20], ensure_ascii=False),
        top_sectors_placeholder=top_sector_bullets or json.dumps(snapshot.top_sectors[:10], ensure_ascii=False),
        bottom_sectors_placeholder=bottom_sector_bullets or json.dumps(snapshot.bottom_sectors[:10], ensure_ascii=False),
        market_volume_placeholder=market_volume_placeholder_str or json.dumps(snapshot.market_volume, ensure_ascii=False),
        macro_data_placeholder="\n".join(macro_bullets) if macro_bullets else "暂无最新宏观数据",
    )


def _build_snapshot(
    indices,
    hot_stocks,
    hot_concepts,
    hot_industries,
    dragon_tiger,
    market_statistics,
    market_news,
    market_volume,
    macro_data,
) -> DailyReviewDataSnapshot:
    """将并行采集的原始数据封装为 DailyReviewDataSnapshot，异常值转为空数据。

    Param:
        indices: 指数数据
        hot_stocks: 热门股票
        hot_concepts: 热门概念
        hot_industries: 热门行业
        dragon_tiger: 龙虎榜
        market_statistics: 市场统计
        market_news: 市场新闻
        market_volume: 市场成交额
        macro_data: 宏观经济数据
    Return:
        封装后的数据快照
    """
    market_statistics_data = {} if isinstance(market_statistics, Exception) or market_statistics is None else market_statistics.model_dump()
    top_sectors = market_statistics_data.get("top_sectors", [])
    bottom_sectors = market_statistics_data.get("bottom_sectors", [])
    market_statistics_data.pop("top_sectors", None)
    market_statistics_data.pop("bottom_sectors", None)
    snapshot_data = {
        "indices": [] if isinstance(indices, Exception) or indices is None else [item.model_dump() for item in indices.indices],
        "hot_stocks": [] if isinstance(hot_stocks, Exception) or hot_stocks is None else hot_stocks,
        "hot_concepts": [] if isinstance(hot_concepts, Exception) or hot_concepts is None else hot_concepts,
        "hot_industries": [] if isinstance(hot_industries, Exception) or hot_industries is None else hot_industries,
        "dragon_tiger": [] if isinstance(dragon_tiger, Exception) or dragon_tiger is None else dragon_tiger,
        "market_statistics": market_statistics_data,
        "market_news": [] if isinstance(market_news, Exception) or market_news is None else [item.model_dump() for item in market_news],
        "top_sectors": top_sectors,
        "bottom_sectors": bottom_sectors,
    }
    if not isinstance(market_volume, Exception) and market_volume is not None:
        snapshot_data["market_volume"] = market_volume.model_dump()
    if not isinstance(macro_data, Exception) and macro_data is not None:
        snapshot_data["macro_data"] = macro_data
    return DailyReviewDataSnapshot(**snapshot_data)


async def generate_daily_review(request: DailyReviewRequest) -> DailyReviewResult:
    """生成每日复盘报告：优先读取缓存，否则并行采集数据并调用 LLM 生成分析。

    Param:
        request: 复盘请求，包含日期和是否强制刷新标志
    Return:
        完整的复盘结果对象
    """
    date = request.date or datetime.now().strftime("%Y-%m-%d")
    if not request.force:
        cached = load_daily_review(date)
        if cached is not None:
            return cached

    indices, hot_stocks, hot_concepts, hot_industries, dragon_tiger, market_statistics, market_news, market_volume, macro_data = await asyncio.gather(
        get_indices(),
        get_hot_stocks(),
        get_ths_hot_concept(),
        get_ths_hot_industry(),
        get_dragon_tiger_list(date),
        get_market_statistics(date),
        get_market_news(),
        get_realtime_market_volume(),
        get_macro_data(),
        return_exceptions=True,
    )
    
    snapshot = _build_snapshot(
        indices=indices,
        hot_stocks=hot_stocks,
        hot_concepts=hot_concepts,
        hot_industries=hot_industries,
        dragon_tiger=dragon_tiger,
        market_statistics=market_statistics,
        market_news=market_news,
        market_volume=market_volume,
        macro_data=macro_data,
    )
    llm_review = ""
    try:
        settings = get_settings()
        llm_client = create_llm_client(settings)
        user_content = _build_prompt(date, snapshot)
        logger.info(user_content)
        logger.info(f"生成复盘报告: date={date}, prompt_length={len(user_content)}")
        llm_review = normalize_llm_review(llm_client.chat(
            [
                {"role": "system", "content": MARKET_SYSTEM_PROMPT},
                {"role": "user", "content": user_content},
            ],
            temperature=settings.llm_temperature,
        ).strip())
    except Exception:
        logger.error(f"生成复盘报告失败: date={date}", exc_info=True)
    review = _build_fallback_review(date, snapshot)
    review.llm_review = llm_review

    save_daily_review(review)
    return review

