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
    """获取所有股票的历史 AI 分析记录列表。

    Return:
        list[AnalysisHistoryItem]: 全部历史分析条目集合。
    """
    return list_all_analyses()


# --- Parameterized routes ---


@router.post("/{code}", response_model=AnalysisResult)
async def trigger_analysis(code: str):
    """触发指定股票的同步 AI 分析。

    Param:
        code: 股票代码（路径参数），6 位数字。
    Return:
        AnalysisResult: 完整的结构化分析结果，包含评级、信号与目标价等字段。
    """
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
    """读取指定股票当天的最新分析结果，优先返回缓存。

    Param:
        code: 股票代码（路径参数），6 位数字。
    Return:
        dict | AnalysisResult: 缓存或落盘的最近一次分析结果；若不存在则抛出 404。
    """
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
    """SSE 端点，流式推送分析进度事件。

    Param:
        code: 股票代码（路径参数），6 位数字；同一代码并发请求会返回 409。
    Return:
        EventSourceResponse: SSE 流，依次发送 progress 事件并以哨兵结束。
    """

    # 防止同一股票并发分析
    if code in _active_analyses and not _active_analyses[code].done():
        raise HTTPException(status_code=409, detail="该股票正在分析中，请稍后")

    async def event_generator():
        """组合分析任务与事件队列，生成 SSE 事件迭代器。

        Return:
            AsyncIterator[dict]: 逐条 yield SSE 事件或 keepalive 注释。
        """
        queue: asyncio.Queue[AnalysisProgress | None] = asyncio.Queue()

        async def progress_callback(event: AnalysisProgress):
            """分析管线进度回调，将事件放入 SSE 队列。

            Param:
                event: 分析管线发出的单条进度事件。
            Return:
                None
            """
            await queue.put(event)

        async def run_and_cleanup():
            """运行分析管线并在结束时向队列写入终止哨兵。

            Return:
                None
            """
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
    """读取指定股票的历史分析索引列表。

    Param:
        code: 股票代码（路径参数），6 位数字。
    Return:
        list[AnalysisHistoryItem]: 按日期排序的历史分析摘要条目。
    """
    return list_analyses(code)


@router.get("/{code}/history/{date}", response_model=AnalysisResult)
async def get_analysis_by_date(code: str, date: str):
    """读取指定股票在指定日期的分析结果，命中缓存优先。

    Param:
        code: 股票代码（路径参数），6 位数字。
        date: 分析日期（路径参数），格式 YYYYMMDD。
    Return:
        AnalysisResult: 该日的完整分析结果；若不存在则返回 404。
    """
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
