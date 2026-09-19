"""FRED official API provider for United States macroeconomic indicators."""

from __future__ import annotations

from collections.abc import Callable
from concurrent.futures import Future, ThreadPoolExecutor
from datetime import date
from threading import BoundedSemaphore
from typing import Any, Protocol

import requests

from app.configuration import Settings, get_settings

FRED_OBSERVATIONS_URL = "https://api.stlouisfed.org/fred/series/observations"
_FRED_TIMEOUT_SECONDS = 20
_FRED_ROW_LIMIT = 24
_FRED_SERIES_WORKERS = 12
_FRED_MAX_CONCURRENT_REQUESTS = 16
# 固定线程池让 CPI、PCE、就业的组成序列并发读取；全局信号量同时约束复合指标
# 和单序列指标，既满足 Provider 的 25 秒预算，也避免并发刷新导致请求线程失控。
_FRED_SERIES_EXECUTOR = ThreadPoolExecutor(
    max_workers=_FRED_SERIES_WORKERS,
    thread_name_prefix="fred-series",
)
_FRED_REQUEST_SEMAPHORE = BoundedSemaphore(_FRED_MAX_CONCURRENT_REQUESTS)


class _Response(Protocol):
    def raise_for_status(self) -> None: ...

    def json(self) -> dict[str, Any]: ...


class _Session(Protocol):
    trust_env: bool

    def get(
        self,
        url: str,
        *,
        params: dict[str, Any],
        timeout: int,
    ) -> _Response: ...


class FredDataProvider:
    """Fetch and normalize FRED observations into the existing macro row shape."""

    def __init__(
        self,
        *,
        settings_provider: Callable[[], Settings] = get_settings,
        session: _Session | None = None,
        session_factory: Callable[[], _Session] | None = None,
    ) -> None:
        if session is not None and session_factory is not None:
            raise ValueError("session 和 session_factory 不能同时配置")
        self._settings_provider = settings_provider
        # requests.Session 不保证跨线程安全。生产环境为每条序列创建独立 Session；
        # session 参数仅用于测试注入，并由调用方管理生命周期。
        self._session_factory = session_factory or (
            (lambda: session) if session is not None else requests.Session
        )
        self._close_sessions = session is None

    @staticmethod
    def _month_period(raw_date: str) -> str:
        parsed = date.fromisoformat(raw_date)
        return f"{parsed.year:04d}-{parsed.month:02d}"

    @staticmethod
    def _quarter_period(raw_date: str) -> str:
        parsed = date.fromisoformat(raw_date)
        quarter = (parsed.month - 1) // 3 + 1
        return f"{parsed.year:04d}Q{quarter}"

    def _fetch_series(
        self,
        series_id: str,
        *,
        units: str | None = None,
        frequency: str | None = None,
        aggregation_method: str | None = None,
        period_formatter: Callable[[str], str] | None = None,
        value_divisor: float = 1,
    ) -> dict[str, float]:
        settings = self._settings_provider()
        api_key = settings.fred_api_key.strip()
        if not api_key:
            raise ValueError("FRED_API_KEY 未配置")

        params: dict[str, Any] = {
            "series_id": series_id,
            "api_key": api_key,
            "file_type": "json",
            "sort_order": "desc",
            "limit": _FRED_ROW_LIMIT,
        }
        if units:
            params["units"] = units
        if frequency:
            params["frequency"] = frequency
        if aggregation_method:
            params["aggregation_method"] = aggregation_method

        session = self._session_factory()
        session.trust_env = settings.http_trust_env
        try:
            try:
                with _FRED_REQUEST_SEMAPHORE:
                    response = session.get(
                        FRED_OBSERVATIONS_URL,
                        params=params,
                        timeout=_FRED_TIMEOUT_SECONDS,
                    )
                response.raise_for_status()
                payload = response.json()
            except requests.RequestException as error:
                status_code = getattr(getattr(error, "response", None), "status_code", None)
                detail = f"HTTP {status_code}" if status_code is not None else type(error).__name__
                # requests 的原始异常可能包含带 api_key 的完整 URL，不向上游传播。
                raise RuntimeError(f"FRED 请求失败: {series_id} ({detail})") from None
        finally:
            if self._close_sessions:
                close = getattr(session, "close", None)
                if callable(close):
                    close()
        observations = payload.get("observations")
        if not isinstance(observations, list):
            raise ValueError(f"FRED 响应缺少 observations: {series_id}")

        formatter = period_formatter or self._month_period
        values: dict[str, float] = {}
        for observation in observations:
            if not isinstance(observation, dict):
                continue
            raw_date = str(observation.get("date") or "").strip()
            raw_value = str(observation.get("value") or "").strip()
            if not raw_date or not raw_value or raw_value == ".":
                continue
            try:
                period = formatter(raw_date)
                value = float(raw_value) / value_divisor
            except (TypeError, ValueError):
                continue
            values[period] = value
        if not values:
            raise ValueError(f"FRED 指标无有效观测值: {series_id}")
        return values

    def _fetch_series_group(
        self,
        fetchers: dict[str, Callable[[], dict[str, float]]],
    ) -> dict[str, dict[str, float]]:
        """并发读取组成同一指标的必要序列；任一失败时整组失败。"""
        futures: dict[str, Future[dict[str, float]]] = {
            field: _FRED_SERIES_EXECUTOR.submit(fetcher)
            for field, fetcher in fetchers.items()
        }
        try:
            return {field: future.result() for field, future in futures.items()}
        except Exception:
            for future in futures.values():
                future.cancel()
            raise

    @staticmethod
    def _combine_series(series: dict[str, dict[str, float]]) -> list[dict[str, Any]]:
        periods = sorted(set().union(*(values.keys() for values in series.values())))
        latest_values: dict[str, float] = {}
        latest_periods: dict[str, str] = {}
        rows: list[dict[str, Any]] = []
        for period in periods:
            row: dict[str, Any] = {"TIME": period}
            for field, values in series.items():
                if period in values:
                    latest_values[field] = values[period]
                    latest_periods[field] = period
                row[field] = latest_values.get(field)
            row["_FIELD_PERIODS"] = dict(latest_periods)
            rows.append(row)
        return list(reversed(rows))[:_FRED_ROW_LIMIT]

    @staticmethod
    def _single_series_rows(series: dict[str, float]) -> list[dict[str, Any]]:
        return [
            {"TIME": period, "VALUE": value}
            for period, value in sorted(series.items(), reverse=True)
        ][:_FRED_ROW_LIMIT]

    def fetch_us_gdp(self) -> list[dict[str, Any]]:
        series = self._fetch_series(
            "A191RL1Q225SBEA",
            period_formatter=self._quarter_period,
        )
        return self._single_series_rows(series)

    def fetch_us_ppi(self) -> list[dict[str, Any]]:
        return self._combine_series(
            self._fetch_series_group(
                {
                    "PPI_YOY": lambda: self._fetch_series("PPIFID", units="pc1"),
                    "PPI_MOM": lambda: self._fetch_series("PPIFID", units="pch"),
                    "CORE_PPI_YOY": lambda: self._fetch_series("PPIFES", units="pc1"),
                    "CORE_PPI_MOM": lambda: self._fetch_series("PPIFES", units="pch"),
                }
            )
        )

    def fetch_us_pmi(self) -> list[dict[str, Any]]:
        return self._combine_series(
            self._fetch_series_group(
                {
                    "MANUFACTURING_PMI": lambda: self._fetch_series("NAPM"),
                    "SERVICES_PMI": lambda: self._fetch_series("NAPMNMI"),
                }
            )
        )

    def fetch_us_cpi(self) -> list[dict[str, Any]]:
        return self._combine_series(
            self._fetch_series_group(
                {
                    "CPI_YOY": lambda: self._fetch_series("CPIAUCSL", units="pc1"),
                    "CPI_MOM": lambda: self._fetch_series("CPIAUCSL", units="pch"),
                    "CORE_CPI_YOY": lambda: self._fetch_series("CPILFESL", units="pc1"),
                    "CORE_CPI_MOM": lambda: self._fetch_series("CPILFESL", units="pch"),
                }
            )
        )

    def fetch_us_pce(self) -> list[dict[str, Any]]:
        return self._combine_series(
            self._fetch_series_group(
                {
                    "PCE_YOY": lambda: self._fetch_series("PCEPI", units="pc1"),
                    "PCE_MOM": lambda: self._fetch_series("PCEPI", units="pch"),
                    "CORE_PCE_YOY": lambda: self._fetch_series("PCEPILFE", units="pc1"),
                    "CORE_PCE_MOM": lambda: self._fetch_series("PCEPILFE", units="pch"),
                }
            )
        )

    def fetch_us_labor(self) -> list[dict[str, Any]]:
        return self._combine_series(
            self._fetch_series_group(
                {
                    "UNEMPLOYMENT": lambda: self._fetch_series("UNRATE"),
                    "NON_FARM": lambda: self._fetch_series("PAYEMS", units="chg", value_divisor=10),
                    "INITIAL_JOBLESS": lambda: self._fetch_series(
                        "ICSA",
                        frequency="m",
                        aggregation_method="avg",
                        value_divisor=10_000,
                    ),
                }
            )
        )

    def fetch_us_employment_details(self) -> list[dict[str, Any]]:
        return self._combine_series(
            self._fetch_series_group(
                {
                    "CIVILIAN_LABOR_PARTICIPATION": lambda: self._fetch_series("CIVPART"),
                    "AVG_HOURLY_EARNINGS_MOM": lambda: self._fetch_series(
                        "CES0500000003",
                        units="pch",
                    ),
                }
            )
        )

    def fetch_us_consumer_confidence(self) -> list[dict[str, Any]]:
        return self._single_series_rows(
            self._fetch_series("UMCSENT", frequency="m", aggregation_method="avg")
        )

    def fetch_us_credit_spread(self) -> list[dict[str, Any]]:
        return self._single_series_rows(self._fetch_series("BAMLH0A0HYM2"))

    def fetch_us_fed_rate(self) -> list[dict[str, Any]]:
        series = self._fetch_series(
            "DFEDTARU",
            frequency="m",
            aggregation_method="eop",
        )
        return self._single_series_rows(series)

    def fetch_us_retail_sales(self) -> list[dict[str, Any]]:
        return self._single_series_rows(self._fetch_series("RSAFS", units="pch"))

    def fetch_us_trade_balance(self) -> list[dict[str, Any]]:
        return self._single_series_rows(
            self._fetch_series("BOPGSTB", value_divisor=100)
        )


fred_provider = FredDataProvider()
