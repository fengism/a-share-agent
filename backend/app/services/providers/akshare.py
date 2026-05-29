import pandas as pd
from tenacity import retry, stop_after_attempt, wait_exponential


class _LazyAkshare:
    def __getattr__(self, name: str):
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
    def __init__(self):
        super().__init__(name="akshare", source_label="Akshare")

    @retry(stop=stop_after_attempt(3), wait=wait_exponential(min=1, max=10))
    def fetch_stock_kline(self, code: str, period: str, start_date: str, end_date: str, adjust: str) -> pd.DataFrame:
        return ak.stock_zh_a_hist(
            symbol=code, period=period, start_date=start_date, end_date=end_date, adjust=adjust
        )

    @retry(stop=stop_after_attempt(3), wait=wait_exponential(min=1, max=10))
    def fetch_stock_kline_sina(self, code: str, start_date: str, end_date: str, adjust: str) -> pd.DataFrame:
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
        sym = normalize_code(code)
        if date is None:
            date = get_last_trade_date(code)
        trade_date = date.replace("-", "")
        try:
            df = ak.stock_intraday_sina(symbol=sym.prefixed_upper, date=trade_date)
        except Exception:
            return pd.DataFrame()

        df = df.copy()
        df["time"] = df["ticktime"].map(lambda value: f"{date} {str(value).strip()}")
        df["amount"] = pd.to_numeric(df.get("price"), errors="coerce") * pd.to_numeric(df.get("volume"), errors="coerce")
        df["price"] = pd.to_numeric(df.get("price"), errors="coerce")
        df["volume"] = pd.to_numeric(df.get("volume"), errors="coerce")
        return normalize_intraday_df(df)

    def fetch_stock_intraday_transactions(self, code: str, date: str | None = None) -> pd.DataFrame:
        try:
            df = ak.stock_intraday_em(symbol=code)
        except Exception:
            return pd.DataFrame()
        return normalize_intraday_df(df)

    def fetch_stock_intraday_minute(self, code: str, date: str | None = None) -> pd.DataFrame:
        try:
            df = ak.stock_zh_a_hist_min_em(symbol=code, period="1", adjust="")
        except Exception:
            return pd.DataFrame()
        return normalize_intraday_df(df)

    @retry(stop=stop_after_attempt(3), wait=wait_exponential(min=1, max=10))
    def fetch_market_indices(self) -> pd.DataFrame:
        return ak.stock_zh_index_spot_em(symbol="沪深重要指数")

    @retry(stop=stop_after_attempt(3), wait=wait_exponential(min=1, max=10))
    def fetch_market_indices_sina(self) -> pd.DataFrame:
        return ak.stock_zh_index_spot_sina()

    @retry(stop=stop_after_attempt(3), wait=wait_exponential(min=1, max=10))
    def fetch_stock_basic_info(self, code: str) -> dict:
        df = ak.stock_individual_info_em(symbol=code)
        if df.empty:
            return {}
        return dict(zip(df["item"], df["value"]))

    @retry(stop=stop_after_attempt(3), wait=wait_exponential(min=1, max=10))
    def fetch_stock_names_sh(self) -> pd.DataFrame:
        return ak.stock_info_sh_name_code()

    @retry(stop=stop_after_attempt(3), wait=wait_exponential(min=1, max=10))
    def fetch_stock_names_sz(self) -> pd.DataFrame:
        return ak.stock_info_sz_name_code()

    @retry(stop=stop_after_attempt(3), wait=wait_exponential(min=1, max=10))
    def fetch_stock_names_bj(self) -> pd.DataFrame:
        return ak.stock_info_bj_name_code()

    @retry(stop=stop_after_attempt(3), wait=wait_exponential(min=1, max=10))
    def fetch_stock_financials(self, symbol: str, indicator: str) -> pd.DataFrame:
        if indicator == "balance":
            return ak.stock_balance_sheet_by_report_em(symbol=symbol)
        if indicator == "profit":
            return ak.stock_profit_sheet_by_report_em(symbol=symbol)
        if indicator == "cashflow":
            return ak.stock_cash_flow_sheet_by_report_em(symbol=symbol)
        raise ValueError(f"Unknown financial indicator: {indicator}")

    @retry(stop=stop_after_attempt(3), wait=wait_exponential(min=1, max=10))
    def fetch_stock_valuation_comparison(self, symbol: str) -> pd.DataFrame:
        return ak.stock_zh_valuation_comparison_em(symbol=symbol)

    @retry(stop=stop_after_attempt(3), wait=wait_exponential(multiplier=1, min=1, max=4), reraise=True)
    def fetch_stock_spot_snapshot(self) -> pd.DataFrame:
        return ak.stock_zh_a_spot_em()

    @retry(stop=stop_after_attempt(3), wait=wait_exponential(multiplier=1, min=1, max=4), reraise=True)
    def fetch_stock_valuation_baidu(self, symbol: str, indicator: str, period: str) -> pd.DataFrame:
        return ak.stock_zh_valuation_baidu(symbol=symbol, indicator=indicator, period=period)

    @retry(stop=stop_after_attempt(3), wait=wait_exponential(min=1, max=10))
    def fetch_index_kline(self, symbol: str, period: str, start_date: str, end_date: str) -> pd.DataFrame:
        return ak.index_zh_a_hist(symbol=symbol, period=period, start_date=start_date, end_date=end_date)

    @retry(stop=stop_after_attempt(3), wait=wait_exponential(min=1, max=10))
    def fetch_index_kline_sina(self, symbol: str) -> pd.DataFrame:
        return ak.stock_zh_index_daily(symbol=normalize_index_symbol(symbol))

    @retry(stop=stop_after_attempt(3), wait=wait_exponential(min=1, max=10))
    def fetch_index_kline_tencent(self, symbol: str) -> pd.DataFrame:
        return ak.stock_zh_index_daily_tx(symbol=normalize_index_symbol(symbol))

    def fetch_stock_news(self, code: str) -> list[NewsSearchItem]:
        results: list[NewsSearchItem] = []
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
        return ak.index_realtime_sw(symbol="二级行业")

    @retry(stop=stop_after_attempt(3), wait=wait_exponential(min=1, max=10))
    def fetch_sw_index_components(self, symbol: str) -> pd.DataFrame:
        return ak.index_component_sw(symbol=symbol)

    @retry(stop=stop_after_attempt(3), wait=wait_exponential(min=1, max=10))
    def fetch_hot_rank_detail(self, symbol: str) -> pd.DataFrame:
        return ak.stock_hot_rank_detail_em(symbol=symbol)


akshare_provider = AkshareDataProvider()
