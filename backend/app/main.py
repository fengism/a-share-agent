import asyncio
import contextlib
import logging
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.routers import stock, market, analysis, screener, daily_review, push, chat, config, industry_chain
from app.utils.rate_limiter import call_blocking

logger = logging.getLogger(__name__)

# 配置日志格式，确保 uvicorn 不会覆盖
log_format = "%(asctime)s %(levelname)-8s [%(name)s] %(message)s"
logging.basicConfig(
    level=logging.INFO,
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
    from app.db import init_db
    from app.services.screener.industry import build_industry_mapping
    from app.services.stock.name_map import build_stock_name_map

    init_db()
    logger.info("数据库初始化完成")

    tasks = [
        asyncio.create_task(build_industry_mapping()),
        asyncio.create_task(refresh_industry_mapping_file_daily()),
        asyncio.create_task(build_stock_name_map()),
    ]
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

app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:5173", "http://127.0.0.1:5173"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(stock.router, prefix="/api/stock", tags=["stock"])
app.include_router(market.router, prefix="/api/market", tags=["market"])
app.include_router(analysis.router, prefix="/api/analysis", tags=["analysis"])
app.include_router(screener.router, prefix="/api/screener", tags=["screener"])
app.include_router(daily_review.router, prefix="/api/daily-review", tags=["daily-review"])
app.include_router(push.router, prefix="/api/push", tags=["push"])
app.include_router(chat.router, prefix="/api/chat", tags=["chat"])
app.include_router(config.router, prefix="/api/config", tags=["config"])
app.include_router(industry_chain.router, prefix="/api/industry-chain", tags=["industry-chain"])


async def refresh_industry_mapping_file_daily():
    """每 24 小时定时更新一次行业映射文件的后台任务。"""
    from app.services.screener.industry import update_industry_mapping_sw_second_file

    while True:
        try:
            await call_blocking(update_industry_mapping_sw_second_file)
            logger.info("行业映射文件更新完成")
        except Exception as exc:
            logger.error(f"行业映射文件更新失败: {exc}", exc_info=True)
        await asyncio.sleep(24 * 60 * 60)


@app.get("/api/health")
async def health():
    """健康检查端点。

    Return:
        包含 status 字段的字典。
    """
    return {"status": "ok"}
