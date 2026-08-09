"""同花顺 Provider 统一入口。"""

from collections.abc import Callable

import requests

import app.infrastructure.providers.ths.forecast as forecast
import app.infrastructure.providers.ths.hot_rank as hot_rank
import app.infrastructure.providers.ths.hsgt as hsgt
import app.infrastructure.providers.ths.volume as volume
from app.configuration.runtime import get_settings
from app.configuration.schema import Settings
from app.infrastructure.providers.ths.transport import ThsTransport


class ThsDataProvider:
    name = "ths"

    def __init__(
        self,
        *,
        settings_provider: Callable[[], Settings],
        session: requests.Session | None = None,
    ) -> None:
        self._transport = ThsTransport(
            settings_provider=settings_provider,
            session=session,
        )

    @property
    def _session(self) -> requests.Session:
        return self._transport._session

    def _get_session(self) -> requests.Session:
        return self._transport.session()

    def _request(self, method: str, url: str, **kwargs) -> requests.Response:
        return self._transport.request(method, url, **kwargs)

    def _request_json(self, method: str, url: str, **kwargs) -> dict:
        return self._transport.request_json(method, url, **kwargs)

    @staticmethod
    def _normalize_hot_rank_items(
        items: list[dict],
        *,
        plate: bool = False,
    ) -> list[dict]:
        return hot_rank.normalize_items(items, plate=plate)

    def fetch_stock_forecast_reports(self, code: str):
        return forecast.fetch_stock_forecast_reports(self._transport, code)

    def fetch_hot_stock_rank(self) -> list[dict]:
        return hot_rank.fetch_hot_stock_rank(self._transport)

    def fetch_hot_plate_rank(self, plate_type: str) -> list[dict]:
        return hot_rank.fetch_hot_plate_rank(self._transport, plate_type)

    def fetch_market_volume_day(self) -> dict:
        return volume.fetch_market_volume_chart(self._transport, "turnover_day")

    def fetch_market_volume_minute(self) -> dict:
        return volume.fetch_market_volume_chart(self._transport, "turnover_minute")

    def _fetch_market_volume_chart(self, chart_key: str) -> dict:
        return volume.fetch_market_volume_chart(self._transport, chart_key)

    def fetch_market_volume(self):
        return volume.fetch_market_volume(
            self.fetch_market_volume_day,
            self.fetch_market_volume_minute,
        )

    def fetch_hot_stock_reasons(self, date: str | None = None):
        return hot_rank.fetch_hot_stock_reasons(self._transport, date)

    def fetch_hsgt_realtime(self):
        return hsgt.fetch_hsgt_realtime(self._transport, self.get_trade_date())

    def get_trade_date(self) -> str:
        return hsgt.get_trade_date(self._transport)


ths_provider = ThsDataProvider(settings_provider=get_settings)
