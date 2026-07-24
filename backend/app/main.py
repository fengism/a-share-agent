import asyncio
import contextlib
import logging
import os
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager
from datetime import datetime

from fastapi import FastAPI
from fastapi.responses import JSONResponse
from fastapi.middleware.cors import CORSMiddleware

from app.routers import stock, market, analysis, screener, daily_review, push, chat, config, industry_chain, macro, stock_aggregate, auth
from app.middleware import UserContextMiddleware
from app.utils.rate_limiter import call_blocking
from app.config import get_settings

logger = logging.getLogger(__name__)

# 配置日志格式，确保 uvicorn 不会覆盖
log_format = "%(asctime)s %(levelname)-8s [%(name)s] %(message)s"
log_level = os.environ.get("LOG_LEVEL", "INFO").upper()
logging.basicConfig(
    level=getattr(logging, log_level, logging.INFO),
    format=log_format,
    datefmt="%Y-%m-%d %H:%M:%S",
    force=True,
)
# 让 uvicorn 的 access log 也用相同格式
for name in ["uvicorn", "uvicorn.access", "uvicorn.error"]:
    uv_logger = logging.getLogger(name)
    uv_logger.handlers.clear()
    handler = logging.StreamHandler()
    handler.setFormatter(logging.Formatter(log_format, datefmt="%Y-%m-%d %H:%M:%S"))
    uv_logger.addHandler(handler)
    uv_logger.setLevel(logging.INFO)

@asynccontextmanager
async def lifespan(_: FastAPI) -> AsyncIterator[None]:
    """FastAPI 应用生命周期管理器，启动时初始化数据库与预热任务，关闭时取消任务。"""
    import concurrent.futures
    from app.db import init_db
    from app.services.screener.industry import build_industry_mapping
    from app.services.stock.name_map import build_stock_name_map
    from app.config import get_settings

    # 增大默认线程池，避免 asyncio.to_thread 耗尽线程
    loop = asyncio.get_running_loop()
    loop.set_default_executor(concurrent.futures.ThreadPoolExecutor(max_workers=20))

    init_db()
    logger.info("数据库初始化完成")

    # 预注册 chat agent 的 skills 和 tools（仅执行一次）
    from app.services.chat.skills import register_all_skills
    register_all_skills()
    logger.info("Chat skills 注册完成")

    tasks = [
        asyncio.create_task(build_industry_mapping()),
        asyncio.create_task(refresh_industry_mapping_file_daily()),
        asyncio.create_task(build_stock_name_map()),
        asyncio.create_task(_periodic_wal_checkpoint()),
    ]
    if getattr(get_settings(), "twitter_feeds", None):
        tasks.append(asyncio.create_task(refresh_twitter_feed_periodic()))
        logger.info("Twitter 资讯定时拉取任务已启动")
    logger.info("行业映射预热任务已启动")
    logger.info("行业映射文件定时更新任务已启动")
    logger.info("股票名称映射预热任务已启动")
    try:
        yield
    finally:
        for task in tasks:
            task.cancel()
        for task in tasks:
            with contextlib.suppress(asyncio.CancelledError):
                await task


app = FastAPI(title="A股智能分析系统", version="0.1.0", lifespan=lifespan)

_cors_origins = [o.strip() for o in get_settings().cors_origins.split(",") if o.strip()]
app.add_middleware(
    CORSMiddleware,
    allow_origins=_cors_origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# 按 Bearer token 将登录用户绑定到请求上下文，供 get_effective_settings 叠加私密配置。
app.add_middleware(UserContextMiddleware)

app.include_router(stock.router, prefix="/api/stock", tags=["stock"])
app.include_router(market.router, prefix="/api/market", tags=["market"])
app.include_router(analysis.router, prefix="/api/analysis", tags=["analysis"])
app.include_router(screener.router, prefix="/api/screener", tags=["screener"])
app.include_router(daily_review.router, prefix="/api/daily-review", tags=["daily-review"])
app.include_router(push.router, prefix="/api/push", tags=["push"])
app.include_router(chat.router, prefix="/api/chat", tags=["chat"])
app.include_router(config.router, prefix="/api/config", tags=["config"])
app.include_router(industry_chain.router, prefix="/api/industry-chain", tags=["industry-chain"])
app.include_router(macro.router, prefix="/api/macro", tags=["macro"])
app.include_router(stock_aggregate.router, prefix="/api/stock", tags=["stock"])
app.include_router(auth.router, prefix="/api/auth", tags=["auth"])


@app.exception_handler(Exception)
async def global_exception_handler(request, exc: Exception):
    logger.error("未捕获异常: %s %s error=%s", request.method, request.url.path, exc, exc_info=True)
    return JSONResponse(
        status_code=500,
        content={"detail": "服务器内部错误，请稍后重试"},
    )


@app.exception_handler(ValueError)
async def value_error_handler(request, exc: ValueError):
    return JSONResponse(
        status_code=400,
        content={"detail": str(exc)},
    )


# 后台任务健康状态追踪
_background_task_health: dict[str, dict] = {}


def _get_task_health(name: str) -> dict:
    """获取指定后台任务的最新健康状态。"""
    return _background_task_health.get(name, {"status": "unknown", "last_run": None, "last_error": None})


async def _run_periodic(name: str, coro_factory, interval_seconds: int, health_check=None):
    """健壮的后台任务循环：异常自动恢复 + 健康状态追踪。

    捕获 asyncio.CancelledError 并重新抛出以支持正常关闭，
    捕获其他异常后记录日志并继续循环（自动恢复）。

    Param:
        name: 任务名称（用于日志和健康状态键）
        coro_factory: 无参异步函数，每次循环调用生成新的协程
        interval_seconds: 循环间隔（秒）
        health_check: 可选的健康检查回调（无参异步函数，返回 bool）
    """
    entry = _background_task_health.setdefault(name, {"status": "running", "last_run": None, "last_error": None})
    loop_count = 0
    consecutive_errors = 0
    while True:
        try:
            if health_check is not None:
                healthy = await health_check()
                if not healthy:
                    raise RuntimeError(f"后台任务 [{name}] 健康检查失败")
            coro = coro_factory()
            await coro
            entry["last_run"] = datetime.now().isoformat()
            entry["status"] = "running"
            consecutive_errors = 0
        except asyncio.CancelledError:
            entry["status"] = "stopped"
            raise
        except Exception as exc:
            consecutive_errors += 1
            entry["status"] = "error"
            entry["last_error"] = str(exc)
            logger.error(f"后台任务 [{name}] 第 {loop_count + 1} 次循环失败（连续 {consecutive_errors} 次）: {exc}", exc_info=True)
            # 指数退避：连续失败时延长等待时间，最长 10 分钟
            backoff = min(600, 2 ** consecutive_errors)
            await asyncio.sleep(backoff)
            continue

        await asyncio.sleep(interval_seconds)
        loop_count += 1


async def refresh_industry_mapping_file_daily():
    """每 24 小时定时更新一次行业映射文件的后台任务。"""
    from app.services.screener.industry import update_industry_mapping_sw_second_file

    async def _iteration():
        await call_blocking(update_industry_mapping_sw_second_file)
        logger.info("行业映射文件更新完成")

    await _run_periodic(
        name="industry_mapping",
        coro_factory=_iteration,
        interval_seconds=24 * 60 * 60,
    )


async def _periodic_wal_checkpoint():
    """每 6 小时执行一次 WAL checkpoint，控制 WAL 文件大小。"""
    from app.db.connection import checkpoint_wal

    async def _iteration():
        await call_blocking(checkpoint_wal)
        logger.info("WAL checkpoint 完成")

    await _run_periodic(
        name="wal_checkpoint",
        coro_factory=_iteration,
        interval_seconds=6 * 60 * 60,
    )



async def refresh_twitter_feed_periodic():
    """每 30 分钟轮询配置的 Twitter 账号，拉取最新推文写入数据库。

    后台任务，应用启动后常驻运行。通过 get_stale_authors 判断每个账号
    是否超过 5 分钟未刷新，仅刷新过期账号。
    使用 _run_periodic 包装实现异常自动恢复与健康状态追踪。
    """
    from app.config import get_settings
    from app.services.providers.twitter import twitter_provider
    from app.db.twitter_store import save_twitter_posts, get_stale_authors

    async def _iteration():
        feeds = get_settings().twitter_feeds
        if not feeds:
            return

        stale = await asyncio.to_thread(get_stale_authors, feeds)
        if not stale:
            logger.debug(f"Twitter no refresh needed: {feeds}")
            return

        logger.info(f"Twitter fetching stale authors: {stale}")
        raw = await asyncio.to_thread(twitter_provider.fetch_posts_for_users, stale)
        await asyncio.to_thread(save_twitter_posts, [p.model_dump() for p in raw])

    await _run_periodic(
        name="twitter_feed",
        coro_factory=_iteration,
        interval_seconds=30 * 60,
        health_check=_twitter_health_check,
    )


async def _twitter_health_check() -> bool:
    """Twitter 后台任务的健康检查：验证数据库连接正常。"""
    try:
        from app.db.connection import get_connection
        conn = get_connection()
        conn.execute("SELECT 1")
        return True
    except Exception:
        return False


@app.get("/api/health")
async def health():
    """健康检查端点，包含后台任务状态。

    Return:
        包含 status 和 background_tasks 字段的字典。
    """
    from app.db.connection import get_connection
    db_ok = False
    try:
        conn = get_connection()
        conn.execute("SELECT 1")
        db_ok = True
    except Exception:
        pass

    return {
        "status": "ok" if db_ok else "error",
        "database": "connected" if db_ok else "error",
        "background_tasks": {
            name: {
                "status": info.get("status", "unknown"),
                "last_run": info.get("last_run"),
                "last_error": info.get("last_error"),
            }
            for name, info in _background_task_health.items()
        },
    }
