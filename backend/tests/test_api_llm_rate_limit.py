"""LLM 触发型端点的每用户频率限制。

覆盖三层：

1. 计数算法本身（滑动窗口、跨用户隔离、惰性清理）；
2. FastAPI 依赖的行为（429 错误码 + ``Retry-After`` 头、配置驱动）；
3. **接线**——真实路由对象上必须挂着 ``llm_rate_limit``，且同一模块里的只读端点
   不能挂（防止有人顺手把所有路由都限流，或重构时把依赖弄丢）。
"""

from __future__ import annotations

import pytest

from app.api.errors import TooManyRequestsError
from app.api.rate_limit import check_and_record, llm_rate_limit, reset_llm_rate_limit
from app.api.routes import analysis_execution, chat, daily_review, industry_chain

pytestmark = pytest.mark.anyio


class FakeClock:
    def __init__(self) -> None:
        self.now = 1_000.0

    def __call__(self) -> float:
        return self.now

    def advance(self, seconds: float) -> None:
        self.now += seconds


@pytest.fixture(autouse=True)
def _clean_limiter() -> None:
    reset_llm_rate_limit()
    yield
    reset_llm_rate_limit()


def test_allows_up_to_limit_then_blocks() -> None:
    clock = FakeClock()
    for _ in range(3):
        assert check_and_record(1, limit=3, window=60, clock=clock) is None
    retry_after = check_and_record(1, limit=3, window=60, clock=clock)
    assert retry_after is not None
    assert retry_after >= 1


def test_window_slides_and_frees_capacity() -> None:
    clock = FakeClock()
    for _ in range(2):
        assert check_and_record(1, limit=2, window=10, clock=clock) is None
    assert check_and_record(1, limit=2, window=10, clock=clock) is not None
    # 恰好滑出窗口后应立刻恢复（边界取 <=，不留下 1 秒的"幽灵锁定"）。
    clock.advance(10)
    assert check_and_record(1, limit=2, window=10, clock=clock) is None


def test_retry_after_shrinks_as_window_drains() -> None:
    clock = FakeClock()
    assert check_and_record(1, limit=1, window=60, clock=clock) is None
    first = check_and_record(1, limit=1, window=60, clock=clock)
    clock.advance(50)
    later = check_and_record(1, limit=1, window=60, clock=clock)
    assert first is not None and later is not None
    assert later < first <= 61


def test_users_do_not_share_quota() -> None:
    clock = FakeClock()
    assert check_and_record(1, limit=1, window=60, clock=clock) is None
    assert check_and_record(1, limit=1, window=60, clock=clock) is not None
    assert check_and_record(2, limit=1, window=60, clock=clock) is None


def test_buckets_are_isolated() -> None:
    clock = FakeClock()
    assert check_and_record(1, limit=1, window=60, bucket="llm", clock=clock) is None
    assert check_and_record(1, limit=1, window=60, bucket="pdf", clock=clock) is None


def test_stale_keys_are_purged_so_the_table_stays_bounded() -> None:
    clock = FakeClock()
    for user_id in range(50):
        check_and_record(user_id, limit=5, window=5, clock=clock)
    clock.advance(1_000)
    # 超过清理间隔后触发一次清扫；随后新用户不应把旧键留在表里。
    for _ in range(300):
        check_and_record(9_999, limit=10**6, window=5, clock=clock)
    from app.api.rate_limit import _HITS

    assert list(_HITS) == [(9_999, "llm")]


async def test_dependency_raises_429_with_retry_after(monkeypatch: pytest.MonkeyPatch) -> None:
    class Settings:
        user_llm_rate_limit_requests = 1
        user_llm_rate_limit_window = 60

    monkeypatch.setattr("app.api.rate_limit.get_settings", lambda: Settings())
    user = {"id": 7, "username": "u", "is_admin": False}
    await llm_rate_limit(user=user)  # type: ignore[arg-type]
    with pytest.raises(TooManyRequestsError) as excinfo:
        await llm_rate_limit(user=user)  # type: ignore[arg-type]
    assert excinfo.value.status_code == 429
    assert excinfo.value.code == "llm.rate_limited"
    assert excinfo.value.headers
    assert int(excinfo.value.headers["Retry-After"]) >= 1


async def test_dependency_isolated_per_user(monkeypatch: pytest.MonkeyPatch) -> None:
    class Settings:
        user_llm_rate_limit_requests = 1
        user_llm_rate_limit_window = 60

    monkeypatch.setattr("app.api.rate_limit.get_settings", lambda: Settings())
    await llm_rate_limit(user={"id": 1, "username": "a", "is_admin": False})  # type: ignore[arg-type]
    await llm_rate_limit(user={"id": 2, "username": "b", "is_admin": False})  # type: ignore[arg-type]


LLM_ROUTES = [
    (chat, "POST", ""),
    (analysis_execution, "POST", "/{code}"),
    (analysis_execution, "GET", "/{code}/stream"),
    (daily_review, "POST", "/generate"),
    (industry_chain, "POST", "/atlas/mine"),
    (industry_chain, "POST", "/atlas/mine-batch"),
    (industry_chain, "GET", "/{name}/stream"),
]


@pytest.mark.parametrize(("module", "method", "path"), LLM_ROUTES)
def test_llm_routes_are_wired_to_the_limiter(module, method: str, path: str) -> None:
    route = next(
        r for r in module.router.routes if r.path == path and method in r.methods
    )
    names = [dependency.call.__name__ for dependency in route.dependant.dependencies]
    assert "llm_rate_limit" in names, f"{module.__name__} {method} {path} 未接限流"


@pytest.mark.parametrize(
    ("module", "method", "path"),
    [
        (chat, "GET", "/sessions"),
        (analysis_execution, "GET", "/{code}/result"),
        (daily_review, "GET", "/history"),
        (industry_chain, "GET", "/history"),
    ],
)
def test_read_only_routes_are_not_rate_limited(module, method: str, path: str) -> None:
    route = next(
        r for r in module.router.routes if r.path == path and method in r.methods
    )
    names = [dependency.call.__name__ for dependency in route.dependant.dependencies]
    assert "llm_rate_limit" not in names
