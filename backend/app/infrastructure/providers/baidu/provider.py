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
from app.infrastructure.providers.baidu.harvester import BaiduCredentialHarvester, baidu_harvester
from app.infrastructure.providers.baidu.transport import BaiduTransport, check_result_code


class BaiduDataProvider:
    name = "baidu"

    def __init__(
        self,
        settings_provider: Callable[[], Settings],
        *,
        harvester: BaiduCredentialHarvester | None = None,
        session: requests.Session | None = None,
    ) -> None:
        self._settings_provider = settings_provider
        self._harvester = harvester or baidu_harvester
        self._transport = BaiduTransport(
            credentials_provider=self._credentials,
            on_risk_detected=self.invalidate_credentials,
            session=session,
        )

    def _credentials(self) -> tuple[str, str]:
        # 1. 优先使用无头浏览器动态采集的有效凭证
        cookie, token = self._harvester.get_credentials()
        if token:
            return cookie, token
        # 2. 检查静态配置
        settings = self._settings_provider()
        if settings.baidu_acs_token:
            return settings.baidu_cookie, settings.baidu_acs_token
        # 3. 动态触发后台预热刷新
        self._harvester.trigger_background_refresh()
        return settings.baidu_cookie, ""

    async def refresh_credentials(self, force: bool = False) -> tuple[str, str]:
        """通过无头浏览器获取或刷新百度动态凭证。"""
        return await self._harvester.ensure_credentials(force=force)

    def invalidate_credentials(self) -> None:
        """使缓存的动态凭证失效。"""
        self._harvester.invalidate()

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
