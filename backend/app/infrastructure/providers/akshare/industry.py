"""AkShare 申万行业能力。"""

import logging
import math

import pandas as pd
import requests
from tenacity import retry, stop_after_attempt, wait_exponential

from app.infrastructure.http.client import get_session
from app.infrastructure.providers.akshare.loader import ak

logger = logging.getLogger(__name__)


@retry(stop=stop_after_attempt(3), wait=wait_exponential(min=1, max=10))
def fetch_sw_index_realtime() -> pd.DataFrame:
    try:
        return ak.index_realtime_sw(symbol="二级行业")
    except requests.RequestException as exc:
        logger.warning("申万行业指数接口连接失败，跳过同源直连并使用备用数据: %s", exc)
        return pd.DataFrame()
    except Exception:
        logger.debug("akshare index_realtime_sw 异常，尝试直接调用申万宏源 API", exc_info=True)
    try:
        url = "https://www.swsresearch.com/institute-sw/api/index_publish/current/"
        headers = {
            "User-Agent": (
                "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
                "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/126.0.0.0 Safari/537.36"
            ),
        }
        params: dict = {"page": "1", "page_size": "50", "indextype": "二级行业"}
        response = get_session().get(url, params=params, headers=headers, timeout=(3.05, 10))
        response.raise_for_status()
        data = response.json().get("data", {})
        total_num = int(data.get("count", 0))
        records = data.get("list", [])
        total_page = math.ceil(total_num / 50) if total_num else 1
        for page in range(2, total_page + 1):
            params["page"] = str(page)
            page_response = get_session().get(url, params=params, headers=headers, timeout=(3.05, 10))
            page_response.raise_for_status()
            records.extend(page_response.json().get("data", {}).get("list", []))
        if not records:
            logger.warning("申万宏源 API 返回空数据")
            return pd.DataFrame()
        frame = pd.DataFrame(records)
        expected_columns = [
            "指数代码",
            "指数名称",
            "昨收盘",
            "今开盘",
            "成交额",
            "最高价",
            "最低价",
            "最新价",
            "成交量",
        ]
        if len(frame.columns) >= 9:
            frame.columns = expected_columns[: len(frame.columns)]
            frame = frame[expected_columns]
        for column in expected_columns[2:]:
            if column in frame.columns:
                frame[column] = pd.to_numeric(frame[column], errors="coerce")
        logger.info("申万宏源 API 兜底获取成功: %d 条", len(frame))
        return frame
    except requests.RequestException as exc:
        logger.warning("申万宏源 API 连接失败，使用备用数据: %s", exc)
        return pd.DataFrame()
    except Exception:
        logger.warning("申万行业指数实时数据获取失败（akshare 与直接 API 均不可用）", exc_info=True)
        return pd.DataFrame()


@retry(stop=stop_after_attempt(3), wait=wait_exponential(min=1, max=10))
def fetch_sw_index_components(symbol: str) -> pd.DataFrame:
    try:
        return ak.index_component_sw(symbol=symbol)
    except KeyError:
        logger.debug("申万行业指数成分数据为空: symbol=%s", symbol)
        return pd.DataFrame()
    except Exception:
        logger.warning("申万行业指数成分数据格式异常: symbol=%s", symbol, exc_info=True)
        return pd.DataFrame()
