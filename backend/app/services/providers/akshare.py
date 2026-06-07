import logging

import pandas as pd
from tenacity import retry, stop_after_attempt, wait_exponential

logger = logging.getLogger(__name__)


class _LazyAkshare:
    """Purpose: 延迟加载 akshare 库的代理对象，仅在实际访问属性时才执行 import。"""
    def __getattr__(self, name: str):
        """延迟导入 akshare 并返回对应属性。

        Param:
            name: akshare 模块的属性名
        Return:
            akshare 模块中对应名称的对象
        """
        import akshare as ak

        return getattr(ak, name)


ak = _LazyAkshare()

from app.services.base.data_provider import BaseDataProvider
from app.services.base.intraday_utils import normalize_intraday_df
from app.models.search_item import NewsSearchItem
from app.utils.symbol_utils import normalize_code
from app.utils.market_utils import get_last_trade_date
from app.utils.symbol_utils import normalize_index_symbol
from app.utils.data_clean import rename_columns


class AkshareDataProvider(BaseDataProvider):
    """Purpose: 通过 akshare 库封装 A 股行情、财务、指数及新闻等基础数据的统一获取接口。"""
    def __init__(self):
        """初始化 AkshareDataProvider，固定 name 与 source_label。"""
        super().__init__(name="akshare", source_label="Akshare")

    @retry(stop=stop_after_attempt(3), wait=wait_exponential(min=1, max=10))
    def fetch_stock_kline(self, code: str, period: str, start_date: str, end_date: str, adjust: str) -> pd.DataFrame:
        """获取个股 K 线数据（akshare 东方财富接口）。

        Param:
            code: 6 位股票代码
            period: K线周期，如 daily/weekly/monthly
            start_date: 起始日期，格式 YYYYMMDD
            end_date: 结束日期，格式 YYYYMMDD
            adjust: 复权方式，qfq/hfq/空字符串
        Return:
            包含日期、OHLCV 等列的 K线 DataFrame
        """
        return ak.stock_zh_a_hist(
            symbol=code, period=period, start_date=start_date, end_date=end_date, adjust=adjust
        )

    @retry(stop=stop_after_attempt(3), wait=wait_exponential(min=1, max=10))
    def fetch_stock_kline_sina(self, code: str, start_date: str, end_date: str, adjust: str) -> pd.DataFrame:
        """获取个股 K 线数据（akshare 新浪接口），并进行字段清洗与重命名。

        Param:
            code: 6 位股票代码
            start_date: 起始日期，格式 YYYYMMDD
            end_date: 结束日期，格式 YYYYMMDD
            adjust: 复权方式
        Return:
            中文列名的 K线 DataFrame；空数据时返回空 DataFrame
        """
        sym = normalize_code(code)
        df = ak.stock_zh_a_daily(symbol=sym.prefixed_lower, start_date=start_date, end_date=end_date, adjust=adjust)
        if df.empty:
            return pd.DataFrame()
        df["date"] = pd.to_datetime(df["date"])
        df["open"] = pd.to_numeric(df["open"], errors="coerce")
        df["high"] = pd.to_numeric(df["high"], errors="coerce")
        df["low"] = pd.to_numeric(df["low"], errors="coerce")
        df["close"] = pd.to_numeric(df["close"], errors="coerce")
        df["volume"] = pd.to_numeric(df["volume"], errors="coerce") / 100
        df["amount"] = pd.to_numeric(df["amount"], errors="coerce")
        df["turnover"] = pd.to_numeric(df["turnover"], errors="coerce") * 100
        del df["outstanding_share"]
        return rename_columns(
            df,
            {"date": "日期", "open": "开盘", "high": "最高", "low": "最低", "close": "收盘", "volume": "成交量", "amount": "成交额", "turnover": "换手率"},
        )

    def fetch_stock_intraday_minute_sina(self, code: str, date: str | None = None) -> pd.DataFrame:
        """获取个股分时数据（akshare 新浪接口），默认取最近一个交易日。

        Param:
            code: 6 位股票代码
            date: 可选，交易日，格式 YYYY-MM-DD；为空时自动推断
        Return:
            标准化后的分时 DataFrame；获取失败时返回空 DataFrame
        """
        sym = normalize_code(code)
        if date is None:
            date = get_last_trade_date(code)
        trade_date = date.replace("-", "")
        try:
            df = ak.stock_intraday_sina(symbol=sym.prefixed_upper, date=trade_date)
        except Exception as exc:
            logger.info("akshare新浪分时数据不可用: code=%s, error=%s", code, exc)
            return pd.DataFrame()

        df = df.copy()
        df["time"] = df["ticktime"].map(lambda value: f"{date} {str(value).strip()}")
        df["amount"] = pd.to_numeric(df.get("price"), errors="coerce") * pd.to_numeric(df.get("volume"), errors="coerce")
        df["price"] = pd.to_numeric(df.get("price"), errors="coerce")
        df["volume"] = pd.to_numeric(df.get("volume"), errors="coerce")
        return normalize_intraday_df(df)

    def fetch_stock_intraday_transactions(self, code: str, date: str | None = None) -> pd.DataFrame:
        """获取个股逐笔成交数据（akshare 东方财富接口）。

        Param:
            code: 6 位股票代码
            date: 保留参数，当前未使用
        Return:
            标准化后的逐笔成交 DataFrame；获取失败时返回空 DataFrame
        """
        try:
            df = ak.stock_intraday_em(symbol=code)
        except Exception as exc:
            logger.info("akshare东方财富逐笔数据不可用: code=%s, error=%s", code, exc)
            return pd.DataFrame()
        return normalize_intraday_df(df)

    def fetch_stock_intraday_minute(self, code: str, date: str | None = None) -> pd.DataFrame:
        """获取个股分钟级 K 线（akshare 东方财富接口）。

        Param:
            code: 6 位股票代码
            date: 保留参数，当前未使用
        Return:
            标准化后的分钟 K线 DataFrame；获取失败时返回空 DataFrame
        """
        try:
            df = ak.stock_zh_a_hist_min_em(symbol=code, period="1", adjust="")
        except Exception as exc:
            logger.info("akshare东方财富分钟K线不可用: code=%s, error=%s", code, exc)
            return pd.DataFrame()
        return normalize_intraday_df(df)

    @retry(stop=stop_after_attempt(3), wait=wait_exponential(min=1, max=10))
    def fetch_market_indices(self) -> pd.DataFrame:
        """获取沪深重要指数实时行情（东方财富）。

        Return:
            指数实时行情 DataFrame
        """  
        return ak.stock_zh_index_spot_em(symbol="沪深重要指数")

    @retry(stop=stop_after_attempt(3), wait=wait_exponential(min=1, max=10))
    def fetch_market_indices_sina(self) -> pd.DataFrame:
        """获取沪深重要指数实时行情（新浪接口）。

        Return:
            指数实时行情 DataFrame
        """
        return ak.stock_zh_index_spot_sina()

    @retry(stop=stop_after_attempt(3), wait=wait_exponential(min=1, max=10))
    def fetch_stock_basic_info(self, code: str) -> dict:
        """获取个股基本信息（东方财富）。

        Param:
            code: 6 位股票代码
        Return:
            以 item/value 为键值对的基本信息字典
        """
        df = ak.stock_individual_info_em(symbol=code)
        if df.empty:
            return {}
        return dict(zip(df["item"], df["value"]))

    @retry(stop=stop_after_attempt(3), wait=wait_exponential(min=1, max=10))
    def fetch_stock_names_sh(self) -> pd.DataFrame:
        """获取上交所股票名称代码对照表。

        Return:
            包含沪市股票代码和名称的 DataFrame
        """
        return ak.stock_info_sh_name_code()

    @retry(stop=stop_after_attempt(3), wait=wait_exponential(min=1, max=10))
    def fetch_stock_names_sz(self) -> pd.DataFrame:
        """获取深交所股票名称代码对照表。

        Return:
            包含深市股票代码和名称的 DataFrame
        """
        return ak.stock_info_sz_name_code()

    @retry(stop=stop_after_attempt(3), wait=wait_exponential(min=1, max=10))
    def fetch_stock_names_bj(self) -> pd.DataFrame:
        """获取北交所股票名称代码对照表。

        Return:
            包含北交所股票代码和名称的 DataFrame
        """
        return ak.stock_info_bj_name_code()

    @retry(stop=stop_after_attempt(3), wait=wait_exponential(min=1, max=10))
    def fetch_stock_financials(self, symbol: str, indicator: str) -> pd.DataFrame:
        """获取个股三大财务报表数据。

        Param:
            symbol: 6 位股票代码
            indicator: 报表类型，balance/profit/cashflow
        Return:
            对应报表的 DataFrame；未知 indicator 抛出 ValueError
        """
        if indicator == "balance":
            return ak.stock_balance_sheet_by_report_em(symbol=symbol)
        if indicator == "profit":
            return ak.stock_profit_sheet_by_report_em(symbol=symbol)
        if indicator == "cashflow":
            return ak.stock_cash_flow_sheet_by_report_em(symbol=symbol)
        raise ValueError(f"Unknown financial indicator: {indicator}")

    @retry(stop=stop_after_attempt(3), wait=wait_exponential(min=1, max=10))
    def fetch_stock_valuation_comparison(self, symbol: str) -> pd.DataFrame:
        """获取个股估值对比数据（东方财富）。

        Param:
            symbol: 6 位股票代码
        Return:
            个股估值对比 DataFrame
        """
        return ak.stock_zh_valuation_comparison_em(symbol=symbol)

    @retry(stop=stop_after_attempt(3), wait=wait_exponential(multiplier=1, min=1, max=4), reraise=True)
    def fetch_stock_spot_snapshot(self) -> pd.DataFrame:
        """获取全市场 A 股实时快照（东方财富）。

        Return:
            全部 A 股的实时行情 DataFrame
        """
        return ak.stock_zh_a_spot_em()

    @retry(stop=stop_after_attempt(3), wait=wait_exponential(multiplier=1, min=1, max=4), reraise=True)
    def fetch_stock_valuation_baidu(self, symbol: str, indicator: str, period: str) -> pd.DataFrame:
        """获取个股百度估值数据。

        Param:
            symbol: 6 位股票代码
            indicator: 估值指标
            period: 周期
        Return:
            百度估值 DataFrame
        """
        return ak.stock_zh_valuation_baidu(symbol=symbol, indicator=indicator, period=period)

    @retry(stop=stop_after_attempt(3), wait=wait_exponential(min=1, max=10))
    def fetch_index_kline(self, symbol: str, period: str, start_date: str, end_date: str) -> pd.DataFrame:
        """获取指数 K 线数据。

        Param:
            symbol: 指数代码
            period: 周期
            start_date: 起始日期
            end_date: 结束日期
        Return:
            指数 K线 DataFrame
        """
        return ak.index_zh_a_hist(symbol=symbol, period=period, start_date=start_date, end_date=end_date)

    @retry(stop=stop_after_attempt(3), wait=wait_exponential(min=1, max=10))
    def fetch_index_kline_sina(self, symbol: str) -> pd.DataFrame:
        """获取指数 K 线数据（新浪接口）。

        Param:
            symbol: 指数代码
        Return:
            指数 K线 DataFrame
        """
        return ak.stock_zh_index_daily(symbol=normalize_index_symbol(symbol))

    @retry(stop=stop_after_attempt(3), wait=wait_exponential(min=1, max=10))
    def fetch_index_kline_tencent(self, symbol: str) -> pd.DataFrame:
        """获取指数 K 线数据（腾讯接口）。

        Param:
            symbol: 指数代码
        Return:
            指数 K线 DataFrame
        """
        return ak.stock_zh_index_daily_tx(symbol=normalize_index_symbol(symbol))

    def fetch_stock_news(self, code: str) -> list[NewsSearchItem]:
        """获取个股相关新闻列表（东方财富，最多20条）。

        Param:
            code: 6 位股票代码
        Return:
            NewsSearchItem 列表
        """
        results = []
        df = ak.stock_news_em(symbol=code)
        if df is not None and not df.empty:
            for _, row in df.head(20).iterrows():
                results.append(
                    NewsSearchItem(
                        title=str(row.get("新闻标题", "")),
                        content=str(row.get("新闻内容", "")),
                        source=str(row.get("文章来源", "")),
                        publish_time=str(row.get("发布时间", "")),
                        url=str(row.get("新闻链接", "")),
                        author=str(row.get("作者", "")),
                        read_count=int(row.get("阅读量", 0)),
                        comment_count=int(row.get("评论量", 0)),
                    )
                )
        return results

    @retry(stop=stop_after_attempt(3), wait=wait_exponential(min=1, max=10))
    def fetch_sw_index_realtime(self) -> pd.DataFrame:
        """获取申万二级行业指数实时行情。

        Return:
            申万行业指数实时 DataFrame
        """
        return ak.index_realtime_sw(symbol="二级行业")

    @retry(stop=stop_after_attempt(3), wait=wait_exponential(min=1, max=10))
    def fetch_sw_index_components(self, symbol: str) -> pd.DataFrame:
        """获取申万行业指数的成分股列表。

        Param:
            symbol: 申万行业指数代码
        Return:
            成分股 DataFrame
        """
        return ak.index_component_sw(symbol=symbol)

    @retry(stop=stop_after_attempt(3), wait=wait_exponential(min=1, max=10))
    def fetch_hot_rank_detail(self, symbol: str) -> pd.DataFrame:
        """获取个股或板块在东方财富人气排名的详情数据。

        Param:
            symbol: 股票或板块代码
        Return:
            人气详情 DataFrame
        """
        return ak.stock_hot_rank_detail_em(symbol=symbol)


akshare_provider = AkshareDataProvider()



if __name__ == "__main__":
    print(akshare_provider.fetch_market_indices())
