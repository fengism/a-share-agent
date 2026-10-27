"""AkShare 个股行情与基础资料能力。"""

import logging

import pandas as pd

from app.core.dataframes import normalize_intraday_df, rename_columns
from app.core.market import normalize_code
from app.infrastructure.providers.akshare.loader import ak
from app.infrastructure.providers.sina.quotes import get_last_trade_date

logger = logging.getLogger(__name__)
_HISTORICAL_REQUEST_TIMEOUT_SECONDS = 10.0


def fetch_stock_kline(
    code: str,
    period: str,
    start_date: str,
    end_date: str,
    adjust: str,
) -> pd.DataFrame:
    frame = ak.stock_zh_a_hist(
        symbol=code,
        period=period,
        start_date=start_date,
        end_date=end_date,
        adjust=adjust,
        timeout=_HISTORICAL_REQUEST_TIMEOUT_SECONDS,
    )
    if not frame.empty and "成交量" in frame.columns:
        # AkShare 东方财富日线成交量单位为手；统一为股。
        frame = frame.copy()
        frame["成交量"] = pd.to_numeric(frame["成交量"], errors="coerce") * 100
    return frame


def fetch_stock_kline_sina(
    code: str,
    start_date: str,
    end_date: str,
    adjust: str,
) -> pd.DataFrame:
    symbol = normalize_code(code)
    frame = ak.stock_zh_a_daily(
        symbol=symbol.prefixed_lower,
        start_date=start_date,
        end_date=end_date,
        adjust=adjust,
    )
    if frame.empty:
        return pd.DataFrame()
    frame["date"] = pd.to_datetime(frame["date"])
    for column in ("open", "high", "low", "close", "amount"):
        frame[column] = pd.to_numeric(frame[column], errors="coerce")
    # AkShare 新浪日线的 volume 原始单位为股；保持统一的股口径。
    frame["volume"] = pd.to_numeric(frame["volume"], errors="coerce")
    frame["turnover"] = pd.to_numeric(frame["turnover"], errors="coerce") * 100
    del frame["outstanding_share"]
    return rename_columns(
        frame,
        {
            "date": "日期",
            "open": "开盘",
            "high": "最高",
            "low": "最低",
            "close": "收盘",
            "volume": "成交量",
            "amount": "成交额",
            "turnover": "换手率",
        },
    )


def fetch_stock_intraday_minute_sina(
    code: str,
    date: str | None = None,
) -> pd.DataFrame:
    symbol = normalize_code(code)
    resolved_date = date or get_last_trade_date(code)
    try:
        frame = ak.stock_intraday_sina(
            symbol=symbol.prefixed_upper,
            date=resolved_date.replace("-", ""),
        )
    except Exception as exc:
        logger.debug("akshare新浪分时数据不可用: code=%s, error=%s", code, exc)
        return pd.DataFrame()
    frame = frame.copy()
    frame["time"] = frame["ticktime"].map(
        lambda value: f"{resolved_date} {str(value).strip()}"
    )
    frame["amount"] = pd.to_numeric(frame.get("price"), errors="coerce") * pd.to_numeric(
        frame.get("volume"), errors="coerce"
    )
    frame["price"] = pd.to_numeric(frame.get("price"), errors="coerce")
    frame["volume"] = pd.to_numeric(frame.get("volume"), errors="coerce")
    return normalize_intraday_df(frame)


def fetch_stock_intraday_transactions(
    code: str,
    date: str | None = None,
) -> pd.DataFrame:
    try:
        frame = ak.stock_intraday_em(symbol=code)
    except Exception as exc:
        logger.debug("akshare东方财富逐笔数据不可用: code=%s, error=%s", code, exc)
        return pd.DataFrame()
    return normalize_intraday_df(frame)


def fetch_stock_intraday_minute(
    code: str,
    date: str | None = None,
) -> pd.DataFrame:
    try:
        frame = ak.stock_zh_a_hist_min_em(symbol=code, period="1", adjust="")
    except Exception as exc:
        logger.debug("akshare东方财富分钟K线不可用: code=%s, error=%s", code, exc)
        return pd.DataFrame()
    return normalize_intraday_df(frame)


def fetch_stock_names_sh() -> pd.DataFrame:
    return ak.stock_info_sh_name_code()


def fetch_stock_names_sz() -> pd.DataFrame:
    return ak.stock_info_sz_name_code()


def fetch_stock_names_bj() -> pd.DataFrame:
    return ak.stock_info_bj_name_code()


def fetch_stock_spot_snapshot() -> pd.DataFrame:
    return ak.stock_zh_a_spot_em()


def fetch_restricted_shares(code: str) -> pd.DataFrame:
    return ak.stock_restricted_release_queue_em(symbol=code)


def fetch_interactive_qa(code: str) -> pd.DataFrame:
    return ak.stock_irm_cninfo(symbol=code)
