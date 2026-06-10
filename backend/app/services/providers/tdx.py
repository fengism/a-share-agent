import logging
import threading
from datetime import datetime

import pandas as pd
from mootdx.quotes import Quotes
from tenacity import retry, stop_after_attempt, wait_exponential

from app.services.base.data_provider import BaseDataProvider
from app.utils.symbol_utils import normalize_code, normalize_index_code

logger = logging.getLogger(__name__)


class TdxDataProvider(BaseDataProvider):
    """Purpose: 基于 mootdx 客户端封装通达信本地行情接口，提供股票与指数 K 线、F10 信息。"""

    DAILY_FREQUENCY = 9
    DEFAULT_OFFSET = 10
    KLINE_COLUMNS = ["date", "open", "close", "high", "low", "volume", "amount", "pre_close", "change_pct"]
    NUMERIC_COLUMNS = ["open", "close", "high", "low", "volume", "amount"]
    F10_CATEGORIES = (
        "最新提示", "公司概况", "财务分析",
        "股东研究", "股本结构", "资本运作",
        "业内点评", "行业分析", "公司大事",
    )

    def __init__(self):
        """初始化 TdxDataProvider，延迟创建多线程 mootdx 客户端。"""
        super().__init__(name="tdx", source_label="通达信")
        self._client = None
        self._client_lock = threading.Lock()

    @property
    def client(self):
        """按需创建 mootdx 客户端，避免模块导入阶段产生网络连接。"""
        if self._client is None:
            with self._client_lock:
                if self._client is None:
                    self._client = Quotes.factory(market="std", multithread=True, heartbeat=True)
        return self._client

    def reset_client(self) -> None:
        """清空已创建的 mootdx 客户端，便于异常恢复或测试隔离。"""
        with self._client_lock:
            self._client = None

    def fetch_basic_info(self, code: str) -> dict[str, str]:
        """通过通达信 F10 接口获取个股各类基本信息。

        Param:
            code: 6 位股票代码
        Return:
            dict[str, str]: F10 分类名称到文本内容的映射
        """
        sym = normalize_code(code)
        result: dict[str, str] = {}
        for category in self.F10_CATEGORIES:
            result[category] = self.client.F10(symbol=sym.raw, name=category) or ""
        return result

    @retry(stop=stop_after_attempt(3), wait=wait_exponential(min=1, max=10))
    def fetch_stock_kline(self, code: str, start_date: str = "", end_date: str = "") -> pd.DataFrame:
        """通过通达信本地接口获取个股 K 线并衍生昨收与涨跌幅。

        Param:
            code: 6 位股票代码
            start_date: 起始日期，格式 YYYYMMDD 或 YYYY-MM-DD
            end_date: 结束日期，格式 YYYYMMDD 或 YYYY-MM-DD
        Return:
            包含 date、OHLCV、amount、pre_close、change_pct 的 DataFrame
        """
        sym = normalize_code(code)
        offset = self._calculate_offset(start_date, end_date)
        raw_df = self.client.bars(symbol=sym.raw, frequency=self.DAILY_FREQUENCY, offset=offset)
        return self._format_kline_df(raw_df, start_date=start_date, end_date=end_date)

    @retry(stop=stop_after_attempt(3), wait=wait_exponential(min=1, max=10))
    def fetch_index_kline(self, symbol: str, start_date: str = "", end_date: str = "") -> pd.DataFrame:
        """通过通达信本地接口获取指数 K 线并衍生昨收与涨跌幅。

        Param:
            symbol: 指数代码，支持 000001、sh000001 等格式
            start_date: 起始日期，格式 YYYYMMDD 或 YYYY-MM-DD
            end_date: 结束日期，格式 YYYYMMDD 或 YYYY-MM-DD
        Return:
            包含 date、OHLCV、amount、pre_close、change_pct 的 DataFrame
        """
        raw_symbol = self._normalize_index_symbol(symbol)
        offset = self._calculate_offset(start_date, end_date)
        raw_df = self.client.index(symbol=raw_symbol, frequency=self.DAILY_FREQUENCY, start=0, offset=offset)
        return self._format_kline_df(raw_df, start_date=start_date, end_date=end_date, volume_multiplier=100)

    def _calculate_offset(self, start_date: str = "", end_date: str = "") -> int:
        """根据日期范围计算 TDX 请求条数，默认返回最近 DEFAULT_OFFSET 条。"""
        start_dt = self._parse_date(start_date)
        end_dt = self._parse_date(end_date)
        if not start_dt or not end_dt:
            return self.DEFAULT_OFFSET
        if end_dt < start_dt:
            raise ValueError(f"结束日期早于起始日期: start_date={start_date}, end_date={end_date}")
        return max((end_dt - start_dt).days + 1, 1)

    @staticmethod
    def _parse_date(value: str | None) -> datetime | None:
        """解析 YYYYMMDD 或 YYYY-MM-DD 日期；空值返回 None。"""
        if not value:
            return None
        normalized = str(value).strip().replace("-", "")
        return datetime.strptime(normalized, "%Y%m%d")

    @staticmethod
    def _normalize_index_symbol(symbol: str) -> str:
        """归一化 TDX 指数代码，避免把 000001 误判成深市股票代码。"""
        raw_symbol = normalize_index_code(symbol.strip().lower())
        if not raw_symbol.isdigit() or len(raw_symbol) != 6:
            raise ValueError(f"无效指数代码: {symbol}，需要6位数字")
        return raw_symbol

    def _format_kline_df(
        self,
        raw_df: pd.DataFrame | None,
        *,
        start_date: str = "",
        end_date: str = "",
        volume_multiplier: int | float = 1,
    ) -> pd.DataFrame:
        """将 mootdx 原始 K 线 DataFrame 统一整理为 provider 标准列。"""
        if raw_df is None or raw_df.empty:
            return pd.DataFrame(columns=self.KLINE_COLUMNS)

        df = self._ensure_datetime_column(raw_df)
        required_columns = ["datetime", *self.NUMERIC_COLUMNS]
        missing = [column for column in required_columns if column not in df.columns]
        if missing:
            logger.warning("TDX K线字段缺失: missing=%s", missing)
            return pd.DataFrame(columns=self.KLINE_COLUMNS)

        result = df[required_columns].copy()
        result["date"] = pd.to_datetime(result["datetime"], errors="coerce")
        for column in self.NUMERIC_COLUMNS:
            result[column] = pd.to_numeric(result[column], errors="coerce")

        result = result.dropna(subset=["date"]).sort_values("date")
        result = result.drop_duplicates(subset=["date"], keep="last")
        if volume_multiplier != 1:
            result["volume"] = result["volume"] * volume_multiplier

        result["pre_close"] = result["close"].shift(1)
        result["change_pct"] = (result["close"] - result["pre_close"]) / result["pre_close"] * 100

        result = self._filter_by_date_range(result, start_date=start_date, end_date=end_date)
        result["date"] = result["date"].dt.strftime("%Y-%m-%d")
        return result[self.KLINE_COLUMNS].reset_index(drop=True)

    @staticmethod
    def _ensure_datetime_column(raw_df: pd.DataFrame) -> pd.DataFrame:
        """兼容 mootdx 将 datetime 放在列或索引上的两种返回形态。"""
        df = raw_df.copy()
        if "datetime" in df.columns:
            return df.reset_index(drop=True)

        index_name = df.index.name or "datetime"
        df = df.reset_index()
        if "datetime" not in df.columns and index_name in df.columns:
            df = df.rename(columns={index_name: "datetime"})
        return df

    def _filter_by_date_range(self, df: pd.DataFrame, *, start_date: str = "", end_date: str = "") -> pd.DataFrame:
        """按日期范围过滤 K 线，保留过滤前算出的 pre_close。"""
        start_dt = self._parse_date(start_date)
        end_dt = self._parse_date(end_date)
        if start_dt is not None:
            df = df[df["date"] >= start_dt]
        if end_dt is not None:
            df = df[df["date"] <= end_dt]
        return df.copy()


tdx_provider = TdxDataProvider()

if __name__ == "__main__":
    print(tdx_provider.fetch_index_kline("000001", start_date="20260601", end_date="20260608"))
