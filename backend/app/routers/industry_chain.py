import asyncio
import json
import logging

from fastapi import APIRouter, HTTPException
from sse_starlette.sse import EventSourceResponse

from app.models.industry_chain import IndustryChainHistoryItem, IndustryChainProgress, IndustryChainResult
from app.services.industry_chain.pipeline import run_industry_chain_analysis
from app.services.industry_chain.storage import list_industry_chains, load_industry_chain

logger = logging.getLogger(__name__)
router = APIRouter()

# 防止同一产业链并发分析
_active: dict[str, asyncio.Task] = {}


@router.get("/history", response_model=list[IndustryChainHistoryItem])
async def get_industry_chain_history(name: str = ""):
    """获取产业链分析历史索引（按名称可选过滤）。

    Param:
        name: 可选名称过滤（query 参数）
    Return:
        list[IndustryChainHistoryItem]: 历史条目摘要列表，按时间倒序
    """
    try:
        return list_industry_chains(name=name or None)
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"获取产业链历史失败: {e}")


@router.get("/{name}/latest")
async def get_industry_chain_latest(name: str):
    """获取指定产业链的最新存档（按时间倒序第一条）。

    Param:
        name: 产业链名称（路径参数）
    Return:
        dict: 包含 archive_id；不存在时返回空
    """
    items = list_industry_chains(name=name)
    if not items:
        return {"archive_id": ""}
    return {"archive_id": items[0].archive_id, "saved_at": items[0].saved_at}


@router.get("/{name}/archive/{archive_id}", response_model=IndustryChainResult)
async def get_industry_chain_archive(name: str, archive_id: str):
    """按名称与存档 ID 加载历史产业链分析结果。

    Param:
        name: 产业链名称（路径参数）
        archive_id: 存档 ID（路径参数）
    Return:
        IndustryChainResult: 完整的产业链分析结果
    """
    result = load_industry_chain(name, archive_id)
    if result is None:
        raise HTTPException(status_code=404, detail="产业链存档不存在")
    return result


@router.get("/{name}/stream")
async def stream_industry_chain(name: str):
    """SSE 端点，流式推送产业链分析进度。

    Param:
        name: 产业链名称（路径参数）；同名并发请求会返回 409。
    Return:
        EventSourceResponse: SSE 流，逐条推送 IndustryChainProgress 事件。
    """

    if name in _active and not _active[name].done():
        raise HTTPException(status_code=409, detail="该产业链正在分析中，请稍后")

    async def event_generator():
        """组合产业链分析任务与事件队列，产出 SSE 事件迭代器。

        Return:
            AsyncIterator[dict]: 逐条 yield SSE 事件或 keepalive 注释。
        """
        queue: asyncio.Queue[IndustryChainProgress | None] = asyncio.Queue()

        async def progress_callback(event: IndustryChainProgress):
            """产业链分析进度回调，将事件放入 SSE 队列。

            Param:
                event: 单条进度事件。
            Return:
                None
            """
            await queue.put(event)

        async def run_and_cleanup():
            """运行产业链分析管线并在结束时写入终止哨兵。

            Return:
                None
            """
            try:
                await run_industry_chain_analysis(name, progress_callback=progress_callback)
            except Exception as e:
                logger.warning("产业链分析后台任务异常退出: %s, error=%s", name, e)
            finally:
                await queue.put(None)

        task = asyncio.create_task(run_and_cleanup())
        _active[name] = task

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
            _active.pop(name, None)
            if not task.done():
                task.cancel()

    return EventSourceResponse(event_generator())
