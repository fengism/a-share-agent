import logging
from collections.abc import Awaitable, Callable
from typing import TypeVar

from fastapi import HTTPException

logger = logging.getLogger(__name__)

T = TypeVar("T")


async def run_endpoint(operation: str, func: Callable[[], Awaitable[T]]) -> T:
    try:
        return await func()
    except HTTPException:
        raise
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    except Exception as exc:
        logger.error("%s失败: %s", operation, exc, exc_info=True)
        raise HTTPException(status_code=500, detail=f"{operation}失败: {exc}") from exc
