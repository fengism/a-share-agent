from app.models.analysis import AnalysisResult, FactorAnalysis
from app.services.analysis import storage


def _build_analysis_result() -> AnalysisResult:
    factor = FactorAnalysis(
        score=7,
        summary="ok",
        strengths=["a"],
        risks=["b"],
        key_signals=["c"],
    )
    return AnalysisResult(
        stock_code="600519",
        stock_name="贵州茅台",
        analysis_date="20260610",
        current_price=1234.5,
        fundamental=factor,
        technical=factor,
        sentiment=factor,
        overall_rating=8,
        overall_summary="summary",
        estimated_price_range=(1200.0, 1300.0),
        signal="buy",
        confidence=0.8,
    )


def test_get_analysis_by_date_returns_cached_value(monkeypatch):
    """get_analysis_by_date should return the cached result without hitting storage."""
    expected = _build_analysis_result()

    monkeypatch.setattr(storage.cache, "get", lambda key: expected)
    monkeypatch.setattr(storage, "load_analysis", lambda code, date: None)

    result = storage.get_analysis_by_date("600519", "20260610")

    assert result is expected


def test_get_analysis_by_date_loads_and_caches_file_result(monkeypatch):
    """get_analysis_by_date should cache the file-backed result on cache miss."""
    expected = _build_analysis_result()
    cache_sets = []

    monkeypatch.setattr(storage.cache, "get", lambda key: None)
    monkeypatch.setattr(storage.cache, "set", lambda *args, **kwargs: cache_sets.append((args, kwargs)))
    monkeypatch.setattr(storage, "load_analysis", lambda code, date: expected)

    result = storage.get_analysis_by_date("600519", "20260610")

    assert result is expected
    assert cache_sets[0][0][0] == "analysis:600519:20260610"
    assert cache_sets[0][0][1] is expected
    assert cache_sets[0][1] == {"ttl": 14400}


def test_get_latest_analysis_uses_today_key(monkeypatch):
    """get_latest_analysis should delegate to today's dated lookup."""
    expected = _build_analysis_result()
    calls = []

    monkeypatch.setattr(storage, "get_analysis_by_date", lambda code, date, cache_ttl=14400: calls.append((code, date, cache_ttl)) or expected)

    result = storage.get_latest_analysis("600519")

    assert result is expected
    assert calls[0][0] == "600519"
    assert len(calls[0][1]) == 8
    assert calls[0][2] == 14400
