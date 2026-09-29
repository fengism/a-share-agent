"""内容推送异步应用用例。"""

import logging
from dataclasses import replace

from app.core.concurrency.rate_limiter import call_blocking, misc_semaphore
from app.infrastructure.chart_runtime import render_chart_pngs
from app.modules.push.schemas import PushRequest, PushResponse
from app.modules.push.service import _resolve_content, execute_push

logger = logging.getLogger(__name__)


async def execute_push_request(request: PushRequest, user_id: int) -> PushResponse:
    analysis_kline = None
    if request.target == "feishu" and request.type == "analysis":
        from app.modules.analysis.chart_images import load_analysis_kline

        analysis_kline = await load_analysis_kline(request.code, request.date)
    resolved = await call_blocking(_resolve_content, request, user_id, analysis_kline, semaphore=misc_semaphore)
    if resolved.chart_request is not None:
        try:
            images = await render_chart_pngs(resolved.chart_request)
            resolved = replace(resolved, chart_pngs=images, chart_request=None)
        except Exception as exc:
            # CancelledError intentionally propagates; cancellation must not send a text fallback.
            logger.warning("推送图表渲染失败，降级为无图推送 type=%s error_type=%s", request.type, type(exc).__name__)
            resolved = replace(resolved, chart_request=None)
    return await call_blocking(execute_push, request, resolved, semaphore=misc_semaphore)
