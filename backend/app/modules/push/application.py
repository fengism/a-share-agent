"""内容推送异步应用用例。"""

from app.core.concurrency.rate_limiter import call_blocking, misc_semaphore
from app.modules.push.schemas import PushRequest, PushResponse
from app.modules.push.service import execute_push


async def execute_push_request(request: PushRequest, user_id: int) -> PushResponse:
    # 个股研究推送的图表需要日 K；singleflight 的锁绑定事件循环，
    # 必须在主循环预取后再传入同步推送线程，不能在工作线程里 asyncio.run。
    analysis_kline = None
    if request.target == "feishu" and request.type == "analysis":
        from app.modules.analysis.chart_images import load_analysis_kline

        analysis_kline = await load_analysis_kline(request.code, request.date)
    return await call_blocking(
        execute_push,
        request,
        user_id,
        analysis_kline,
        semaphore=misc_semaphore,
    )
