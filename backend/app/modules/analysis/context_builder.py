import json
from datetime import datetime
from decimal import Decimal

from app.modules.analysis.collector import AnalysisDataBundle


def _format_institution_forecasts(forecasts: list) -> list[dict] | None:
    if not forecasts:
        return None
    return [
        {
            "指标": forecast.metric,
            "年度": forecast.year,
            "预测机构数": forecast.institution_count,
            "最小值": forecast.min_value,
            "均值": forecast.mean_value,
            "最大值": forecast.max_value,
            "行业平均数": forecast.industry_avg,
            "单位": forecast.unit,
        }
        for forecast in forecasts
    ]


def _json_default_handler(value: object):
    if isinstance(value, datetime):
        return value.strftime("%Y-%m-%d %H:%M:%S")
    if isinstance(value, Decimal):
        return float(value)
    if hasattr(value, "item") and callable(value.item):
        return value.item()
    raise TypeError(f"Object of type {type(value)} is not JSON serializable")


def _extract_technical_series(indicators: dict) -> dict:
    series = indicators.get("series", {})
    dates = series.get("dates", [])
    count = min(30, len(dates))
    if count == 0:
        return {}

    result = {}
    macd_trend = [
        {"日期": dates[index], "DIF": series["dif"][index], "DEA": series["dea"][index], "MACD": series["macd_hist"][index]}
        for index in range(-count, 0)
        if series.get("dif", [None])[index] is not None
    ]
    if macd_trend:
        result["MACD趋势(近30日)"] = macd_trend
    rsi_trend = [
        {"日期": dates[index], "RSI": series["rsi"][index]}
        for index in range(-count, 0)
        if series.get("rsi", [None])[index] is not None
    ]
    if rsi_trend:
        result["RSI趋势(近30日)"] = rsi_trend
    kdj_trend = [
        {"日期": dates[index], "K": series["k"][index], "D": series["d"][index], "J": series["j"][index]}
        for index in range(-count, 0)
        if series.get("k", [None])[index] is not None
    ]
    if kdj_trend:
        result["KDJ趋势(近30日)"] = kdj_trend
    ma_trend = [
        {"日期": dates[index], "MA5": series["ma5"][index], "MA20": series["ma20"][index], "MA60": series["ma60"][index]}
        for index in range(-count, 0)
        if series.get("ma5", [None])[index] is not None
    ]
    if ma_trend:
        result["均线趋势(近30日)"] = ma_trend
    return result


def build_analysis_prompt_context(data: AnalysisDataBundle, indicators: dict, analysis_date: str) -> dict:
    """把已采集的数据转换为稳定、受长度约束的 Prompt 上下文。"""
    basic_info = data.basic_info
    valuation = data.valuation_detail
    financial_metrics = data.financial_metrics
    latest_kline = data.kline_data.items[-120:]

    fundamental_json = json.dumps(
        {
            "市盈率TTM": valuation.multiples.pe_ttm if valuation else None,
            "市净率": valuation.multiples.pb if valuation else None,
            "市销率TTM": valuation.multiples.ps_ttm if valuation else None,
            "PEG": valuation.multiples.peg if valuation else None,
            "估值分位": {
                "PE_3年分位": valuation.percentiles.pe_3y if valuation else None,
                "PB_3年分位": valuation.percentiles.pb_3y if valuation else None,
                "PS_3年分位": valuation.percentiles.ps_3y if valuation else None,
            },
            "估值结论": valuation.valuation_view if valuation else None,
            "估值摘要": valuation.valuation_summary if valuation else None,
            "股票类型": valuation.profile.label if valuation and valuation.profile else None,
            "公允价值": {
                "加权公允价值": valuation.blended_fair_value if valuation else None,
                "公允价值区间": valuation.fair_value_range if valuation else None,
                "估值方法权重": valuation.method_weights if valuation else None,
            },
            "同行对比": {
                "PE中位数": valuation.peer_summary.pe_median if valuation else None,
                "PB中位数": valuation.peer_summary.pb_median if valuation else None,
                "PS中位数": valuation.peer_summary.ps_median if valuation else None,
                "同行数量": valuation.peer_summary.peer_count if valuation else None,
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
                if financial_metrics is not None
                else {}
            ),
            "交易所行业": basic_info.exchange_industry,
            "一级行业": basic_info.first_industry.name if basic_info.first_industry else None,
            "二级行业": basic_info.second_industry.name if basic_info.second_industry else None,
            "机构一致预期": _format_institution_forecasts(valuation.institution_forecasts) if valuation else None,
        },
        ensure_ascii=False,
        default=_json_default_handler,
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
    retail_sentiment = data.retail_sentiment if isinstance(data.retail_sentiment, dict) else {}
    sentiment = data.sentiment if isinstance(data.sentiment, dict) else {}
    sentiment_json = json.dumps(
        {
            "热度排名": sentiment.get("hot_rank"),
            "热度分数": sentiment.get("heat_score"),
            "看多比例": retail_sentiment.get("bullish_ratio"),
            "看空比例": retail_sentiment.get("bearish_ratio"),
            "情绪分数": retail_sentiment.get("score"),
            "股吧帖子数": retail_sentiment.get("guba_post_count"),
            "最近新闻": [
                {
                    "标题": getattr(news, "title", ""),
                    "来源": getattr(news, "source", ""),
                    "摘要": (getattr(news, "content", "") or "")[:150],
                }
                for news in (data.news_data[:15] if isinstance(data.news_data, list) else [])
            ],
            "最近帖子标题": retail_sentiment.get("sample_posts", []),
            "散户情绪总结": retail_sentiment.get("summary"),
        },
        ensure_ascii=False,
    )
    market_json = json.dumps(
        {
            "市场指数": (
                [{"名称": index.name, "涨跌幅": index.change_pct} for index in data.market_indices.indices[:5]]
                if data.market_indices and data.market_indices.indices
                else []
            ),
        },
        ensure_ascii=False,
    )
    current_price = data.kline_data.items[-1].close if data.kline_data.items else 0
    return {
        "stock_name": basic_info.name,
        "stock_code": basic_info.code,
        "current_price": current_price,
        "analysis_date": analysis_date,
        "fundamental_data": fundamental_json,
        "technical_data": technical_json,
        "sentiment_data": sentiment_json,
        "market_data": market_json,
    }
