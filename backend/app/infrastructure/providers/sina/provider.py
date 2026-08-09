import json
import logging
import re
from datetime import datetime

import pandas as pd
import requests

from app.constants.http import SINA_FINANCE_HEADERS
from app.constants.market import (
    SINA_INDEX_QUOTE_URL,
    SINA_MARKET_HQ_URL,
    SINA_STOCK_KLINE_URL,
)
from app.core.cache import cache, dated_cache_key
from app.core.dataframes import coerce_numeric_columns, normalize_intraday_df, rename_and_keep_columns, rename_columns
from app.core.market import normalize_code
from app.infrastructure.providers.sina.parsing import parse_jsonp

logger = logging.getLogger(__name__)


class SinaDataProvider:
    """Purpose: 直接对接新浪财经接口的 K线、指数、快照、分时等数据提供器（备用源）。"""
    HQ_PAGE_SIZE = 80
    HQ_MAX_PAGES = 80
    HQ_RETRY_DELAY_SECONDS = 0.3
    NAMES_CACHE_TTL = 86400  # 全市场名称代码，1 天
    SNAPSHOT_CACHE_TTL = 60  # 实时行情，1 分钟
    name = "sina"

    def __init__(self):
        """初始化独立的新浪请求会话。"""
        # Sina 接口常常无法通过代理访问，使用独立 session 并禁用代理
        self._session = requests.Session()
        self._session.trust_env = False


    def fetch_kline(self, code: str, period: str, start_date: str="", end_date: str="") -> pd.DataFrame:
        """新浪股票 K 线（自行处理 JSONP/范围截取与列重命名）。
        Param:
            code: 6 位股票代码
            period: daily/weekly/monthly
            start_date: 起始日期，格式 YYYYMMDD
            end_date: 结束日期，格式 YYYYMMDD
        Return:
            包含日期与 OHLCV 等列的 DataFrame
        """
        sym = normalize_code(code)
        symbol = sym.prefixed_lower
        scale_map = {"daily": "240", "weekly": "1200", "monthly": "5200"}
        scale = scale_map.get(period, "240")

        try:
            start_dt = datetime.strptime(start_date, "%Y%m%d")
            end_dt = datetime.strptime(end_date, "%Y%m%d")
            delta_days = (datetime.now() - start_dt).days
            if period == "daily":
                datalen = max(delta_days * 5 // 7 + 20, 30)
            elif period == "weekly":
                datalen = max(delta_days // 7 + 5, 10)
            else:
                datalen = max(delta_days // 30 + 3, 5)
            datalen = min(datalen, 2000)
        except Exception as e:
            logger.warning("解析日期范围失败: %s", e)
            datalen = 500
        params = {
            "symbol": symbol,
            "scale": scale,
            "ma": "no",
            "datalen": str(datalen),
        }
        r = self._session.get(SINA_STOCK_KLINE_URL, params=params, headers=SINA_FINANCE_HEADERS, timeout=10)
        text = r.text.strip()
        if text.startswith("=") or text.startswith("/*"):
            m = re.search(r"\[.*\]", text)
            if not m:
                return pd.DataFrame()
            records = json.loads(m.group(0))
        else:
            records = json.loads(text)

        if not records:
            return pd.DataFrame()

        df = pd.DataFrame(records)
        df["volume"] = pd.to_numeric(df["volume"], errors="coerce") / 100
        df = rename_columns(
            df,
            {"day": "日期", "open": "开盘", "high": "最高", "low": "最低", "close": "收盘", "volume": "成交量"},
        )
        df["日期"] = pd.to_datetime(df["日期"], errors="coerce")
        start_dt = pd.to_datetime(start_date, format="%Y%m%d", errors="coerce")
        end_dt = pd.to_datetime(end_date, format="%Y%m%d", errors="coerce")
        df = df[df["日期"].notna()]
        if pd.notna(start_dt):
            df = df[df["日期"] >= start_dt]
        if pd.notna(end_dt):
            df = df[df["日期"] <= end_dt]
        df["日期"] = df["日期"].dt.strftime("%Y-%m-%d")
        return df


    def fetch_market_indices(self) -> pd.DataFrame:
        """新浪沪深重要指数实时行情并合并为一张 DataFrame
        https://vip.stock.finance.sina.com.cn/quotes_service/api/json_v2.php/Market_Center.getHQNodeDataSimple?page=1&num=40&sort=symbol&asc=1&node=dpzs&_s_r_a=init
        Return:
            包含代码、名称、最新价、涨跌额、涨跌幅、成交量（手）、成交额（万元） 等列的 DataFrame
        """
        payload = {
            "page": "1",
            "num": "40",
            "sort": "symbol",
            "asc": "1",
            "node": "dpzs",
            "_s_r_a": "init",
        }
        big_df = pd.DataFrame()
        response = self._session.get(SINA_INDEX_QUOTE_URL, params=payload, timeout=10)
        response.raise_for_status()
        data_json = json.loads(response.text)
        if not data_json:
                return big_df
        big_df = pd.DataFrame(data_json)
        big_df = coerce_numeric_columns(big_df, ["trade", "pricechange", "changepercent", "buy", "sell", "settlement", "open", "high", "low"])
        big_df.columns = ["代码", "名称", "最新价", "涨跌额", "涨跌幅", "_", "_", "昨收", "今开", "最高", "最低", "成交量", "成交额", "_", "_"]
        big_df = big_df[["代码", "名称", "最新价", "涨跌额", "涨跌幅", "昨收", "今开", "最高", "最低", "成交量", "成交额"]]
        return coerce_numeric_columns(big_df, ["最新价", "涨跌额", "涨跌幅", "昨收", "今开", "最高", "最低", "成交量", "成交额"])


    def fetch_stock_names(self) -> list[dict]:
        """获取全市场 A 股的名称代码对照表（新浪行情列表分页拉取，按日缓存）。

        Return:
            [{"code": 股票代码, "name": 股票名称}, ...] 列表
        """
        records = self._fetch_market_hq_records(ttl=self.NAMES_CACHE_TTL, cache_scope="stock_names")
        return [
            {"code": str(item.get("code", "")), "name": str(item.get("name", "")).replace(" ", "")}
            for item in records
            if item.get("code") and item.get("name")
        ]

    def fetch_spot_snapshot(self) -> pd.DataFrame:
        """获取全市场 A 股实时行情快照（新浪行情列表，60 秒内复用缓存）。

        Return:
            包含代码、名称、最新价、OHLCV、市盈率、市净率、换手率等的 DataFrame
        """
        records = self._fetch_market_hq_records(ttl=self.SNAPSHOT_CACHE_TTL, cache_scope="spot_snapshot")
        return self._records_to_snapshot_df(records)

    def _records_to_snapshot_df(self, records: list[dict]) -> pd.DataFrame:
        """将新浪行情原始记录转换为标准化的全市场快照 DataFrame。

        Param:
            records: 新浪 hq_records 列表
        Return:
            标准化快照 DataFrame；空记录返回空 DataFrame
        """
        if not records:
            return pd.DataFrame()

        df = pd.DataFrame(records)
        df = rename_and_keep_columns(
            df,
            {
                "code": "代码",
                "name": "名称",
                "trade": "最新价",
                "pricechange": "涨跌额",
                "changepercent": "涨跌幅",
                "buy": "买入",
                "sell": "卖出",
                "settlement": "昨收",
                "open": "今开",
                "high": "最高",
                "low": "最低",
                "volume": "成交量",
                "amount": "成交额",
                "per": "市盈率-动态",
                "pb": "市净率",
                "mktcap": "总市值",
                "nmc": "流通市值",
                "turnoverratio": "换手率",
            },
        )
        if "成交量" in df.columns:
            df["成交量"] = pd.to_numeric(df["成交量"], errors="coerce") * 100
        if "总市值" in df.columns:
            df["总市值"] = pd.to_numeric(df["总市值"], errors="coerce") * 10000
        if "流通市值" in df.columns:
            df["流通市值"] = pd.to_numeric(df["流通市值"], errors="coerce") * 10000
        return df

    def _fetch_market_hq_records(self, ttl: int | None = None, cache_scope: str = "default") -> list[dict]:
        """分页拉取新浪沪深 A 股行情原始 JSON 记录，带缓存。

        Param:
            ttl: 缓存秒数；为 None 表示不缓存（每次都请求网络）
            cache_scope: 缓存键的作用域标识，不同 scope 互不影响
        Return:
            单只股票行情记录字典列表
        """
        cache_key: str | None = dated_cache_key("sina", "hq_records", cache_scope) if ttl else None
        if cache_key is not None:
            cached = cache.get(cache_key)
            if cached is not None:
                return cached

        records: list[dict] = []
        page = 1
        while True:
            response = self._session.get(
                SINA_MARKET_HQ_URL,
                params={
                    "page": page,
                    "num": self.HQ_PAGE_SIZE,
                    "sort": "symbol",
                    "asc": 1,
                    "node": "hs_a",
                    "_s_r_a": "init",
                },
                timeout=15,
            )
            if response.status_code != 200 or not response.text.strip():
                break
            page_records = json.loads(response.text)
            if not page_records:
                break
            records.extend(page_records)
            if len(page_records) < self.HQ_PAGE_SIZE:
                break
            page += 1
            if page > self.HQ_MAX_PAGES:
                break

        if cache_key is not None:
            cache.set(cache_key, records, ttl=ttl)
        return records

    def fetch_stock_intraday_minute_direct(self, code: str = "000001", date: str | None = None) -> pd.DataFrame:
        """直接拉取新浪个股分时分钟线（解析 JSONP 响应）。

        Param:
            code: 6 位股票代码，默认 000001
            date: 可选，交易日，格式 YYYY-MM-DD
        Return:
            标准化后的分时 DataFrame
        """
        sym = normalize_code(code)
        sina_code = sym.prefixed_lower
        params = {
            "symbol": sina_code,
            "callback": f"var t1{sina_code}",
            "version": "7.11.0",
            "dpc": "1",
        }
        response = self._session.get("https://cn.finance.sina.com.cn/minline/getMinlineData", params=params, timeout=10)
        response.raise_for_status()
        payload = parse_jsonp(response.text)
        rows = payload.get("result", {}).get("data", [])
        if not rows:
            return pd.DataFrame()
        df = pd.DataFrame(rows)
        if df.empty:
            return pd.DataFrame()
        trade_date = date or pd.Timestamp.now().strftime("%Y-%m-%d")
        result_df = pd.DataFrame({
            "时间": df["m"].map(lambda value: f"{trade_date} {str(value).strip()}"),
            "成交价": pd.to_numeric(df.get("p"), errors="coerce"),
            "均价": pd.to_numeric(df.get("avg_p"), errors="coerce"),
            "成交量": pd.to_numeric(df.get("v"), errors="coerce"),
            "成交额": pd.to_numeric(df.get("p"), errors="coerce") * pd.to_numeric(df.get("v"), errors="coerce"),
        })
        return normalize_intraday_df(result_df)
    

sina_provider = SinaDataProvider()
