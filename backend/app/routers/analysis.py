import asyncio
import json
import logging
from datetime import datetime

from fastapi import APIRouter, HTTPException
from sse_starlette.sse import EventSourceResponse

from app.models.analysis import AnalysisHistoryItem, AnalysisProgress, AnalysisResult
from app.services.analysis.pipeline import run_analysis
from app.services.analysis.storage import list_analyses, list_all_analyses, load_analysis
from app.utils.cache import cache

logger = logging.getLogger(__name__)

router = APIRouter()

# 跟踪正在运行的分析任务，防止并发重复
_active_analyses: dict[str, asyncio.Task] = {}


# --- Static routes BEFORE parameterized /{code} routes ---


@router.get("/history/all", response_model=list[AnalysisHistoryItem])
async def get_all_analysis_history():
    return list_all_analyses()


# --- Parameterized routes ---


@router.post("/{code}", response_model=AnalysisResult)
async def trigger_analysis(code: str):
    logger.info(f"触发AI分析: code={code}")
    try:
        result = await run_analysis(code)
        logger.info(f"AI分析完成: code={code}, rating={result.overall_rating}, signal={result.signal}, price={result.current_price}")
        return result
    except ValueError as e:
        logger.warning(f"AI分析参数错误: code={code}, error={e}")
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        logger.error(f"AI分析失败: code={code}, error={e}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"分析失败: {e}")


@router.get("/{code}/result")
async def get_analysis_result(code: str):
    today = datetime.now().strftime("%Y%m%d")
    cache_key = f"analysis:{code}:{today}"
    cached = cache.get(cache_key)
    if cached is not None:
        logger.info(f"返回缓存分析结果: code={code}, date={today}")
        return cached

    # Fallback: try loading from file storage
    file_result = load_analysis(code, today)
    if file_result is not None:
        cache.set(cache_key, file_result, ttl=14400)
        return file_result

    logger.info(f"无缓存分析结果: code={code}, date={today}")
    raise HTTPException(status_code=404, detail="暂无分析结果，请先触发分析")


@router.get("/{code}/stream")
async def stream_analysis(code: str):
    """SSE 端点，流式推送分析进度事件"""

    # 防止同一股票并发分析
    if code in _active_analyses and not _active_analyses[code].done():
        raise HTTPException(status_code=409, detail="该股票正在分析中，请稍后")

    async def event_generator():
        queue: asyncio.Queue[AnalysisProgress | None] = asyncio.Queue()

        async def progress_callback(event: AnalysisProgress):
            await queue.put(event)

        async def run_and_cleanup():
            try:
                await run_analysis(code, progress_callback=progress_callback)
            except Exception:
                pass  # 错误已通过 progress_callback 发送
            finally:
                await queue.put(None)  # 哨兵值，结束流

        task = asyncio.create_task(run_and_cleanup())
        _active_analyses[code] = task

        try:
            while True:
                try:
                    event = await asyncio.wait_for(queue.get(), timeout=15.0)
                except asyncio.TimeoutError:
                    yield {"comment": "keepalive"}
                    continue

                if event is None:
                    break

                event_type = event.type
                event_data = json.dumps(event.model_dump(), ensure_ascii=False, default=str)
                yield {"event": event_type, "data": event_data}
        finally:
            _active_analyses.pop(code, None)
            if not task.done():
                task.cancel()

    return EventSourceResponse(event_generator())


@router.get("/{code}/history", response_model=list[AnalysisHistoryItem])
async def get_analysis_history(code: str):
    return list_analyses(code)


@router.get("/{code}/history/{date}", response_model=AnalysisResult)
async def get_analysis_by_date(code: str, date: str):
    # Try cache first
    cache_key = f"analysis:{code}:{date}"
    cached = cache.get(cache_key)
    if cached is not None:
        return cached

    # Load from file
    result = load_analysis(code, date)
    if result is None:
        raise HTTPException(status_code=404, detail=f"未找到 {code} 在 {date} 的分析记录")
    cache.set(cache_key, result, ttl=14400)
    return result
