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


_RESTRICTED_REQUEST_TIMEOUT_SECONDS = 8.0


def fetch_restricted_shares(code: str, timeout: float = _RESTRICTED_REQUEST_TIMEOUT_SECONDS) -> pd.DataFrame:
    """获取个股限售解禁批次数据。
    
    使用显式超时与重试保护，避免东方财富外部数据接口无超时挂起导致线程阻塞。
    """
    import requests
    from requests.adapters import HTTPAdapter
    from urllib3.util.retry import Retry

    url = "https://datacenter-web.eastmoney.com/api/data/v1/get"
    params = {
        "sortColumns": "FREE_DATE",
        "sortTypes": "-1",
        "pageSize": "500",
        "pageNumber": "1",
        "reportName": "RPT_LIFT_STAGE",
        "filter": f'(SECURITY_CODE="{code}")',
        "columns": "SECURITY_CODE,SECURITY_NAME_ABBR,FREE_DATE,CURRENT_FREE_SHARES,ABLE_FREE_SHARES,"
        "LIFT_MARKET_CAP,FREE_RATIO,NEW,B20_ADJCHRATE,A20_ADJCHRATE,FREE_SHARES_TYPE,TOTAL_RATIO,"
        "NON_FREE_SHARES,BATCH_HOLDER_NUM",
        "source": "WEB",
        "client": "WEB",
    }
    headers = {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
    }

    try:
        with requests.Session() as session:
            adapter = HTTPAdapter(max_retries=Retry(total=1, backoff_factor=0.2))
            session.mount("https://", adapter)
            session.mount("http://", adapter)
            response = session.get(url, params=params, headers=headers, timeout=timeout)
            if response.status_code != 200:
                logger.warning("fetch_restricted_shares 响应非200状态: code=%s, status=%s", code, response.status_code)
                return pd.DataFrame()
            data_json = response.json()
    except Exception as exc:
        logger.warning("fetch_restricted_shares 网络或超时异常: code=%s, error=%s", code, exc)
        return pd.DataFrame()

    result_data = data_json.get("result")
    if not result_data or not result_data.get("data"):
        return pd.DataFrame()

    temp_df = pd.DataFrame(result_data["data"])
    temp_df.reset_index(inplace=True)
    temp_df["index"] = temp_df["index"] + 1

    column_mapping = {
        "index": "序号",
        "FREE_DATE": "解禁时间",
        "CURRENT_FREE_SHARES": "实际解禁数量",
        "ABLE_FREE_SHARES": "解禁数量",
        "LIFT_MARKET_CAP": "实际解禁数量市值",
        "FREE_RATIO": "占流通市值比例",
        "B20_ADJCHRATE": "解禁前20日涨跌幅",
        "A20_ADJCHRATE": "解禁后20日涨跌幅",
        "FREE_SHARES_TYPE": "限售股类型",
        "TOTAL_RATIO": "占总市值比例",
        "NON_FREE_SHARES": "未解禁数量",
        "BATCH_HOLDER_NUM": "解禁股东数",
    }
    for orig, target in column_mapping.items():
        if orig in temp_df.columns:
            temp_df.rename(columns={orig: target}, inplace=True)

    if "解禁前一交易日收盘价" not in temp_df.columns:
        temp_df["解禁前一交易日收盘价"] = None

    for col in ("解禁数量", "实际解禁数量", "未解禁数量", "实际解禁数量市值"):
        if col in temp_df.columns:
            temp_df[col] = pd.to_numeric(temp_df[col], errors="coerce") * 10000

    for col in ("占总市值比例", "占流通市值比例", "解禁前20日涨跌幅", "解禁后20日涨跌幅"):
        if col in temp_df.columns:
            temp_df[col] = pd.to_numeric(temp_df[col], errors="coerce")

    if "解禁时间" in temp_df.columns:
        temp_df["解禁时间"] = pd.to_datetime(temp_df["解禁时间"], errors="coerce").dt.date

    return temp_df


def fetch_interactive_qa(code: str) -> pd.DataFrame:
    return ak.stock_irm_cninfo(symbol=code)
