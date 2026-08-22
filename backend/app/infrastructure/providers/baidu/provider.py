"""百度股市通 Provider 统一入口。"""

from collections.abc import Callable

import requests

import app.infrastructure.providers.baidu.fund_flow as fund_flow
import app.infrastructure.providers.baidu.news as news
import app.infrastructure.providers.baidu.rankings as rankings
import app.infrastructure.providers.baidu.stock as stock
from app.configuration.runtime import get_settings
from app.configuration.schema import Settings
from app.core.news import parse_timestamp
from app.infrastructure.providers.baidu.transport import BaiduTransport, check_result_code


class BaiduDataProvider:
    name = "baidu"

    def __init__(
        self,
        settings_provider: Callable[[], Settings],
        *,
        session: requests.Session | None = None,
    ) -> None:
        self._settings_provider = settings_provider
        self._transport = BaiduTransport(
            credentials_provider=self._credentials,
            session=session,
        )

    def _credentials(self) -> tuple[str, str]:
        settings = self._settings_provider()
        return settings.baidu_cookie, settings.baidu_acs_token

    @property
    def _session(self) -> requests.Session:
        return self._transport._session

    def _get_cookie_headers(self) -> dict[str, str]:
        return self._transport.cookie_headers()

    def _request(
        self,
        path: str,
        params: dict,
        headers: dict | None = None,
        timeout: int | None = None,
    ) -> dict:
        return self._transport.get_json(path, params, headers, timeout)

    @staticmethod
    def _check_result_code(data: dict) -> None:
        check_result_code(data)

    def fetch_stock_kline(
        self,
        code: str,
        start_date: str = "",
        end_date: str = "",
    ):
        return stock.fetch_stock_kline(self._transport, code, start_date, end_date)

    def fetch_stock_names(self) -> list[dict]:
        return stock.fetch_stock_names(self._transport)

    def fetch_stock_concept_blocks(self, code: str) -> dict:
        return stock.fetch_stock_concept_blocks(self._transport, code)

    def fetch_stock_fund_flow(self, code: str) -> dict:
        return fund_flow.fetch_stock_fund_flow(self._transport, code)

    def fetch_stock_fund_flow_history(self, code: str, limit: int = 120) -> list[dict]:
        return fund_flow.fetch_stock_fund_flow_history(self._transport, code, limit)

    def fetch_market_kuaixun(self, code: str = "", code_name: str = ""):
        return news.fetch_market_kuaixun(
            self._transport,
            parse_timestamp,
            code,
            code_name,
        )

    @staticmethod
    def _join_express_content(content: dict) -> str:
        return news._join_express_content(content)

    def _fetch_fund_flow_rank(self, block_type: str) -> list[dict]:
        return fund_flow.fetch_block_fund_flow(self._transport, block_type)

    def fetch_industry_fund_flow(self) -> list[dict]:
        return fund_flow.fetch_block_fund_flow(self._transport, "HY")

    def fetch_concept_fund_flow(self) -> list[dict]:
        return fund_flow.fetch_block_fund_flow(self._transport, "GN")

    def fetch_trade_dates(self) -> list[dict]:
        return rankings.fetch_trade_dates(self._transport)

    def fetch_industry_rankings(self, top_n: int = 20) -> dict:
        return rankings.fetch_block_rankings(self._transport, "HY", top_n)

    def fetch_concept_rankings(self, top_n: int = 20) -> dict:
        return rankings.fetch_block_rankings(self._transport, "GN", top_n)


baidu_provider = BaiduDataProvider(get_settings)
