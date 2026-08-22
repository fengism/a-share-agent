"""内容推送异步应用用例。"""

from app.core.concurrency.rate_limiter import call_blocking, misc_semaphore
from app.modules.push.schemas import PushRequest, PushResponse
from app.modules.push.service import execute_push


async def execute_push_request(request: PushRequest, user_id: int) -> PushResponse:
    return await call_blocking(
        execute_push,
        request,
        user_id,
        semaphore=misc_semaphore,
    )
