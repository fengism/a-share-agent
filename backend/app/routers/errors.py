import logging
from collections.abc import Awaitable, Callable
from typing import TypeVar

from fastapi import HTTPException

logger = logging.getLogger(__name__)

T = TypeVar("T")


async def run_endpoint(operation: str, func: Callable[[], Awaitable[T]]) -> T:
    """统一封装路由 endpoint 执行流程，将异常转换为标准 HTTPException。
    Param:
        operation: 业务操作名称，用于日志与错误提示。
        func: 无参 async 可调用对象，承载实际业务逻辑。
    Return:
        T: 业务函数返回值；ValueError 转为 400，LookupError 转为 404，未知异常转为 500。
    """
    try:
        return await func()
    except HTTPException:
        raise
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    except LookupError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    except Exception as exc:
        logger.error("%s失败: %s", operation, exc, exc_info=True)
        raise HTTPException(status_code=500, detail=f"{operation}失败: {exc}") from exc
