import pytest

from app.core.cache import market_cache
from app.core.exceptions import UpstreamUnavailableError
from app.financial_data.market.quotes import global_macro, hot_rank, sector


@pytest.fixture(autouse=True)
def _clear_cache():
    market_cache.clear()
    yield
    market_cache.clear()


def _cache_keys_containing(fragment: str) -> int:
    return sum(1 for key in market_cache._store if fragment in key)


class TestHotRank:
    async def test_upstream_failure_is_not_cached(self, monkeypatch):
        # 旧实现：except 里只记 warning，然后无条件 cache.set(result=[])，
        # 同花顺抖一次就把「空榜单」缓存 5 分钟。
        def _boom():
            raise RuntimeError("同花顺故障")

        monkeypatch.setattr(hot_rank, "get_provider", lambda _name: _boom)

        assert await hot_rank.get_hot_stocks() == []
        assert _cache_keys_containing("hot_rank") == 0

    async def test_success_is_cached(self, monkeypatch):
        rows = [{"code": "600519", "name": "贵州茅台"}]
        monkeypatch.setattr(
            hot_rank,
            "get_provider",
            lambda _name: type("P", (), {"fetch_hot_stock_rank": staticmethod(lambda *a, **k: rows)})(),
        )

        assert await hot_rank.get_hot_stocks() == rows
        assert _cache_keys_containing("hot_rank") == 1


class TestGlobalMacro:
    async def test_partial_failure_is_not_cached(self, monkeypatch):
        async def _boom(*_args, **_kwargs):
            raise RuntimeError("东财故障")

        monkeypatch.setattr(global_macro, "fetch_fx_and_dollar_index", _boom)

        response = await global_macro.get_global_macro_rates()
        # 失败分片以空结构返回，但整份结果不进缓存
        assert response["dollar_and_fx"] == {}
        assert _cache_keys_containing("global_macro_rates") == 0

    async def test_policy_rates_come_from_providers(self, monkeypatch):
        # 政策利率曾经是写死的字符串（美联储长期停在 4.25%-4.50%），会静默过期。
        monkeypatch.setattr(
            global_macro,
            "get_provider",
            lambda name: {
                "nbs": type("P", (), {"fetch_china_lpr": staticmethod(
                    lambda: [{"LPR1Y": 3.0, "LPR5Y": 3.5}]
                )}),
                "eastmoney": type("P", (), {"fetch_us_fed_rate": staticmethod(
                    lambda: [{"TIME": "2026-08", "VALUE": 4.0}]
                )}),
            }[name],
        )

        rates = await global_macro.fetch_policy_rates()
        assert rates["china_lpr_1y"].startswith("3.00%")
        assert rates["china_lpr_5y"].startswith("3.50%")
        assert "4.00%" in rates["us_fed_funds_rate"]
        assert global_macro._RATE_UNAVAILABLE not in rates.values()

    async def test_policy_rates_mark_unavailable_instead_of_inventing(self, monkeypatch):
        def _boom():
            raise RuntimeError("数据源不可用")

        monkeypatch.setattr(global_macro, "get_provider", lambda _name: _boom)

        rates = await global_macro.fetch_policy_rates()
        # 取不到就明确说取不到，绝不回落成写死的数字
        assert set(rates.values()) == {global_macro._RATE_UNAVAILABLE}


class TestIndustryRankings:
    async def test_all_sources_down_raises_instead_of_empty_success(self, monkeypatch):
        def _boom():
            raise RuntimeError("数据源故障")

        monkeypatch.setattr(sector, "_get_kaipanhong_provider", _boom)
        monkeypatch.setattr(sector, "_get_cls_provider", _boom)
        monkeypatch.setattr(sector, "_get_baidu_provider", _boom)
        monkeypatch.setattr(sector, "_get_eastmoney_provider", _boom)
        monkeypatch.setattr(sector, "_get_tencent_provider", _boom)

        # 旧实现返回 {"sectors": [], "source": ""} 的成功响应，并按盘中 TTL 写缓存，
        # 一次全站故障就能把行业排行页毒化一整天。
        with pytest.raises(UpstreamUnavailableError):
            await sector._load_industry_rankings(sector.market_today())
