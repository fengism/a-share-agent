import asyncio
from collections.abc import Awaitable, Callable

MetricFetcher = Callable[[str, Callable], Awaitable[object]]

_BASIC_SOURCES = (
    ("cpi", "fetch_china_cpi"),
    ("ppi", "fetch_china_ppi"),
    ("pmi", "fetch_china_pmi"),
    ("money_supply", "fetch_china_economy_currency_supply"),
)

_FULL_SOURCES = (
    *_BASIC_SOURCES,
    ("lpr", "fetch_china_lpr"),
    ("shibor", "fetch_china_shibor"),
    ("trade", "fetch_china_trade"),
    ("social_financing", "fetch_china_social_financing"),
    ("gdp", "fetch_china_gdp"),
)


async def _collect(provider, sources: tuple[tuple[str, str], ...], fetch_metric: MetricFetcher) -> dict[str, object]:
    values = await asyncio.gather(
        *(fetch_metric(operation, getattr(provider, method_name)) for operation, method_name in sources),
        return_exceptions=True,
    )
    return {
        operation: value
        for (operation, _), value in zip(sources, values)
    }


async def collect_basic(provider, fetch_metric: MetricFetcher) -> dict[str, object]:
    return await _collect(provider, _BASIC_SOURCES, fetch_metric)


async def collect_full(provider, fetch_metric: MetricFetcher) -> dict[str, object]:
    return await _collect(provider, _FULL_SOURCES, fetch_metric)
