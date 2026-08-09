"""内部错误记录与安全响应。"""

import logging
from uuid import uuid4


def build_internal_error(message: str) -> tuple[str, str]:
    """生成可供用户反馈的错误编号与脱敏提示。"""
    error_id = uuid4().hex[:12]
    return error_id, f"{message}（错误编号：{error_id}）"


def log_internal_error(
    logger: logging.Logger,
    operation: str,
    exc: Exception,
    public_message: str,
) -> tuple[str, str]:
    """记录完整异常，并返回不包含内部实现细节的用户提示。"""
    error_id, detail = build_internal_error(public_message)
    logger.error("%s失败 error_id=%s: %s", operation, error_id, exc, exc_info=True)
    return error_id, detail
