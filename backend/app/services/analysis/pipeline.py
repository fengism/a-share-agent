import asyncio
import json
import logging
import pandas as pd
import time
from datetime import datetime
from typing import Awaitable, Callable

from types import SimpleNamespace

from app.models.analysis import AnalysisProgress, AnalysisResult, AnalysisStage
from app.services import technical
from app.services.market.indices import get_indices
from app.services.analysis.news import get_stock_news
from app.services.analysis.retail import get_retail_sentiment, get_stock_sentiment
from app.services.stock.basic_info import get_basic_info
from app.services.stock.financials import get_financial_metrics
from app.services.stock.kline import get_kline
from app.services.stock.valuation import get_valuation_detail
from app.services.providers.ths import ths_provider as _ths_provider
from app.services.llm.client import LLMClient, create_llm_client
from app.services.analysis.prompts import SCHEMA_INSTRUCTION, SYSTEM_PROMPT, USER_PROMPT_TEMPLATE
from app.services.analysis.parser import parse_with_retry
from app.utils.cache import cache
from app.utils.rate_limiter import call_blocking
from app.config import get_settings

logger = logging.getLogger(__name__)

stock_data = SimpleNamespace(
    get_basic_info=get_basic_info,
    get_kline=get_kline,
    get_financial_metrics=get_financial_metrics,
    get_valuation_detail=get_valuation_detail,
)
market_data = SimpleNamespace(get_indices=get_indices)
sentiment_data = SimpleNamespace(
    get_stock_news=get_stock_news,
    get_stock_sentiment=get_stock_sentiment,
    get_retail_sentiment=get_retail_sentiment,
)

def _format_institution_forecasts(df) -> list[dict] | None:
    if df is None or not isinstance(df, pd.DataFrame) or df.empty:
        return None
    rows = []
    for _, row in df.iterrows():
        metric = str(row.get("指标", ""))
        label = "每股收益" if metric == "EPS" else "净利润" if metric == "NET_PROFIT" else metric
        rows.append({
            "指标": label,
            "年度": str(row.get("年度", "")),
            "预测机构数": row.get("预测机构数"),
            "最小值": row.get("最小值"),
            "均值": row.get("均值"),
            "最大值": row.get("最大值"),
            "行业平均数": row.get("行业平均数"),
            "单位": str(row.get("单位", "")).strip(),
        })
    return rows


def _format_institution_forecasts_from_detail(forecasts: list) -> list[dict] | None:
    if not forecasts:
        return None
    return [
        {
            "指标": f.metric,
            "年度": f.year,
            "预测机构数": f.institution_count,
            "最小值": f.min_value,
            "均值": f.mean_value,
            "最大值": f.max_value,
            "行业平均数": f.industry_avg,
            "单位": f.unit,
        }
        for f in forecasts
    ]


def _extract_technical_series(indicators: dict) -> dict:
    series = indicators.get("series", {})
    dates = series.get("dates", [])
    n = min(30, len(dates))
    if n == 0:
        return {}
    result = {}
    macd_trend = [
        {"日期": dates[i], "DIF": series["dif"][i], "DEA": series["dea"][i], "MACD": series["macd_hist"][i]}
        for i in range(-n, 0) if series.get("dif", [None])[i] is not None
    ]
    if macd_trend:
        result["MACD趋势(近30日)"] = macd_trend
    rsi_trend = [
        {"日期": dates[i], "RSI": series["rsi"][i]}
        for i in range(-n, 0) if series.get("rsi", [None])[i] is not None
    ]
    if rsi_trend:
        result["RSI趋势(近30日)"] = rsi_trend
    kdj_trend = [
        {"日期": dates[i], "K": series["k"][i], "D": series["d"][i], "J": series["j"][i]}
        for i in range(-n, 0) if series.get("k", [None])[i] is not None
    ]
    if kdj_trend:
        result["KDJ趋势(近30日)"] = kdj_trend
    ma_trend = [
        {"日期": dates[i], "MA5": series["ma5"][i], "MA20": series["ma20"][i], "MA60": series["ma60"][i]}
        for i in range(-n, 0) if series.get("ma5", [None])[i] is not None
    ]
    if ma_trend:
        result["均线趋势(近30日)"] = ma_trend
    return result


ProgressCallback = Callable[[AnalysisProgress], Awaitable[None]]

STAGE_NAMES = {
    1: "数据采集",
    2: "技术指标计算",
    3: "构造分析请求",
    4: "AI模型分析",
}


async def _emit(cb: ProgressCallback | None, event: AnalysisProgress):
    if cb is not None:
        await cb(event)


async def run_analysis(code: str, progress_callback: ProgressCallback | None = None) -> AnalysisResult:
    # 检查缓存
    today = datetime.now().strftime("%Y%m%d")
    cache_key = f"analysis:{code}:{today}"
    cached = cache.get(cache_key)
    if cached is not None:
        await _emit(progress_callback, AnalysisProgress(type="cached", result=cached))
        return cached

    settings = get_settings()
    llm_client = create_llm_client(settings)

    try:
        # Stage 1: 并行数据采集
        t0 = time.monotonic()
        await _emit(progress_callback, AnalysisProgress(
            type="stage_started",
            stage=AnalysisStage(stage=1, name=STAGE_NAMES[1], status="started",
                                detail="正在从多个数据源采集股票数据..."),
        ))
        one_year_ago = datetime.now().replace(year=datetime.now().year - 1).strftime("%Y%m%d")
        basic_info, kline_data, financial_metrics, valuation_detail, news_data, sentiment_data_result, retail_sentiment_result, market_indices = (
            await asyncio.gather(
                stock_data.get_basic_info(code),
                stock_data.get_kline(code, period="daily", start_date=one_year_ago),
                stock_data.get_financial_metrics(code),
                stock_data.get_valuation_detail(code, compute_percentile=True),
                sentiment_data.get_stock_news(code),
                sentiment_data.get_stock_sentiment(code),
                sentiment_data.get_retail_sentiment(code),
                market_data.get_indices(),
                return_exceptions=True,
            )
        )

        # 处理可能的异常
        basic_info = basic_info if not isinstance(basic_info, Exception) else None
        stock_name = basic_info.name if basic_info else None

        kline_data = kline_data if not isinstance(kline_data, Exception) else None
        financial_metrics = financial_metrics if not isinstance(financial_metrics, Exception) else None
        valuation_detail = valuation_detail if not isinstance(valuation_detail, Exception) else None
        news_data = news_data if not isinstance(news_data, Exception) else []
        sentiment_data_result = sentiment_data_result if not isinstance(sentiment_data_result, Exception) else {}
        retail_sentiment_result = retail_sentiment_result if not isinstance(retail_sentiment_result, Exception) else {}
        market_indices = market_indices if not isinstance(market_indices, Exception) else None
        if not basic_info or not kline_data:
            raise ValueError(f"无法获取股票 {code} 的基本数据")

        await _emit(progress_callback, AnalysisProgress(
            type="stage_completed",
            stage=AnalysisStage(stage=1, name=STAGE_NAMES[1], status="completed",
                                duration_ms=int((time.monotonic() - t0) * 1000)),
        ))

        # Stage 2: 计算技术指标
        t0 = time.monotonic()
        await _emit(progress_callback, AnalysisProgress(
            type="stage_started",
            stage=AnalysisStage(stage=2, name=STAGE_NAMES[2], status="started"),
        ))
        indicators = technical.calculate_all(kline_data.items)
        await _emit(progress_callback, AnalysisProgress(
            type="stage_completed",
            stage=AnalysisStage(stage=2, name=STAGE_NAMES[2], status="completed",
                                duration_ms=int((time.monotonic() - t0) * 1000)),
        ))

        # Stage 3: 构造 Prompt
        t0 = time.monotonic()
        await _emit(progress_callback, AnalysisProgress(
            type="stage_started",
            stage=AnalysisStage(stage=3, name=STAGE_NAMES[3], status="started"),
        ))

        # 截断数据以控制上下文长度
        latest_kline = kline_data.items[-120:]  # 最近120个交易日

        vd = valuation_detail
        fundamental_json = json.dumps(
            {
                "市盈率TTM": vd.multiples.pe_ttm if vd else None,
                "市净率": vd.multiples.pb if vd else None,
                "市销率TTM": vd.multiples.ps_ttm if vd else None,
                "PEG": vd.multiples.peg if vd else None,
                "估值分位": {
                    "PE_3年分位": vd.percentiles.pe_3y if vd else None,
                    "PB_3年分位": vd.percentiles.pb_3y if vd else None,
                    "PS_3年分位": vd.percentiles.ps_3y if vd else None,
                },
                "估值结论": vd.valuation_view if vd else None,
                "估值摘要": vd.valuation_summary if vd else None,
                "股票类型": vd.profile.label if vd and vd.profile else None,
                "公允价值": {
                    "加权公允价值": vd.blended_fair_value if vd else None,
                    "公允价值区间": vd.fair_value_range if vd else None,
                    "估值方法权重": vd.method_weights if vd else None,
                },
                "同行对比": {
                    "PE中位数": vd.peer_summary.pe_median if vd else None,
                    "PB中位数": vd.peer_summary.pb_median if vd else None,
                    "PS中位数": vd.peer_summary.ps_median if vd else None,
                    "同行数量": vd.peer_summary.peer_count if vd else None,
                },
                "财务摘要": (
                    {
                        "最新报告日期": financial_metrics.latest_report_date,
                        "营收": financial_metrics.metrics.get("营收"),
                        "营收同比": financial_metrics.metrics.get("营收同比"),
                        "净利润": financial_metrics.metrics.get("净利润"),
                        "净利润同比": financial_metrics.metrics.get("净利润同比"),
                        "扣非净利润": financial_metrics.metrics.get("扣非净利润"),
                        "扣非净利润同比": financial_metrics.metrics.get("扣非净利润同比"),
                        "经营现金流": financial_metrics.metrics.get("经营现金流"),
                        "资产负债率": financial_metrics.metrics.get("资产负债率"),
                        "现净比": financial_metrics.metrics.get("现净比"),
                    }
                    if financial_metrics is not None else {}
                ),
                "一级行业": basic_info.first_industry.name if basic_info.first_industry else None,
                "二级行业": basic_info.second_industry.name if basic_info.second_industry else None,
                "机构一致预期": _format_institution_forecasts_from_detail(vd.institution_forecasts) if vd else None,
            },
            ensure_ascii=False,
            default=str,
        )

        technical_json = json.dumps(
            {
                "均线": indicators["ma"],
                "MACD": indicators["macd"],
                "RSI": indicators["rsi"],
                "布林带": indicators["boll"],
                "KDJ": indicators["kdj"],
                "成交量均线": indicators["volume_ma"],
                "最近K线摘要": [
                    {"日期": item.date, "收盘价": item.close, "成交量": item.volume, "涨跌幅": item.change_pct}
                    for item in latest_kline[-10:]
                ],
                **_extract_technical_series(indicators),
            },
            ensure_ascii=False,
        )
        stock_name = basic_info.name if basic_info else None
        post_count = retail_sentiment_result.get("post_count") if isinstance(retail_sentiment_result, dict) else 0
        recent_post_titles = retail_sentiment_result.get("sample_posts", []) if isinstance(retail_sentiment_result, dict) else []
        retail_summary = retail_sentiment_result.get("summary") if isinstance(retail_sentiment_result, dict) else None
        sentiment_json = json.dumps(
            {
                "热度排名": sentiment_data_result.get("hot_rank") if isinstance(sentiment_data_result, dict) else None,
                "热度分数": sentiment_data_result.get("heat_score") if isinstance(sentiment_data_result, dict) else None,
                "看多比例": retail_sentiment_result.get("bullish_ratio") if isinstance(retail_sentiment_result, dict) else None,
                "看空比例": retail_sentiment_result.get("bearish_ratio") if isinstance(retail_sentiment_result, dict) else None,
                "情绪分数": retail_sentiment_result.get("score") if isinstance(retail_sentiment_result, dict) else None,
                "股吧帖子数": retail_sentiment_result.get("guba_post_count") if isinstance(retail_sentiment_result, dict) else None,
                "最近新闻": [
                    {
                        "标题": getattr(n, "title", ""),
                        "来源": getattr(n, "source", ""),
                        "摘要": (getattr(n, "content", "") or "")[:150],
                    }
                    for n in (news_data[:15] if isinstance(news_data, list) else [])
                ],
                "最近帖子标题": recent_post_titles,
                "散户情绪总结": retail_summary,
            },
            ensure_ascii=False,
        )

        market_json = json.dumps(
            {
                "市场指数": (
                    [{"名称": idx.name, "涨跌幅": idx.change_pct} for idx in market_indices.indices[:5]]
                    if market_indices and market_indices.indices
                    else []
                ),
            },
            ensure_ascii=False,
        )

        current_price = kline_data.items[-1].close if kline_data.items else 0

        user_content = USER_PROMPT_TEMPLATE.format(
            stock_name=basic_info.name,
            stock_code=basic_info.code,
            current_price=current_price,
            analysis_date=today,
            fundamental_data=fundamental_json,
            technical_data=technical_json,
            sentiment_data=sentiment_json,
            market_data=market_json,
        )

        logger.info(f"[Pipeline] prompt ready: code={code}, prompt_length={len(user_content)}，basic_info={user_content}")

        messages = [
            {"role": "system", "content": SYSTEM_PROMPT},
            {"role": "user", "content": user_content + "\n\n" + SCHEMA_INSTRUCTION},
        ]

        await _emit(progress_callback, AnalysisProgress(
            type="stage_completed",
            stage=AnalysisStage(stage=3, name=STAGE_NAMES[3], status="completed",
                                duration_ms=int((time.monotonic() - t0) * 1000)),
        ))

        # Stage 4: 调用 LLM + 解析 (用 asyncio.to_thread 避免阻塞事件循环)
        t0 = time.monotonic()
        await _emit(progress_callback, AnalysisProgress(
            type="stage_started",
            stage=AnalysisStage(stage=4, name=STAGE_NAMES[4], status="started",
                                detail="正在调用AI模型，可能需要10-25秒..."),
        ))
        raw_response = await asyncio.to_thread(llm_client.chat, messages, temperature=settings.llm_temperature, json_format=True)
        result = await asyncio.to_thread(parse_with_retry, raw_response, llm_client, messages)
        await _emit(progress_callback, AnalysisProgress(
            type="stage_completed",
            stage=AnalysisStage(stage=4, name=STAGE_NAMES[4], status="completed",
                                duration_ms=int((time.monotonic() - t0) * 1000)),
        ))

        # 确保字段正确
        if result.stock_code != basic_info.code:
            result = result.model_copy(update={"stock_code": basic_info.code, "stock_name": basic_info.name})

        # 缓存结果
        cache.set(cache_key, result, ttl=14400)

        # 持久化到文件
        try:
            from app.services.analysis.storage import save_analysis
            await asyncio.to_thread(save_analysis, result)
        except Exception as save_err:
            logger.warning(f"分析结果持久化失败: {save_err}")

        logger.info(f"[Pipeline] 分析完成: {code}, 评分={result.overall_rating}, 信号={result.signal}")

        await _emit(progress_callback, AnalysisProgress(type="complete", result=result))
        return result

    except Exception as e:
        await _emit(progress_callback, AnalysisProgress(type="error", error=str(e)))
        raise
