"""统一 API 错误模型、异常类型与 FastAPI 处理器。"""

from __future__ import annotations

import logging

from fastapi import FastAPI, Request
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse
from pydantic import BaseModel, Field
from starlette.exceptions import HTTPException as StarletteHTTPException

from app.core.errors import build_internal_error
from app.core.exceptions import (
    ApplicationError,
    InvalidRequestError,
    ResourceConflictError,
    ResourceNotFoundError,
    UpstreamUnavailableError,
)

logger = logging.getLogger(__name__)


class ErrorDetail(BaseModel):
    path: str
    message: str
    type: str


class ErrorResponse(BaseModel):
    code: str = Field(description="稳定、可供客户端判断的错误码")
    message: str = Field(description="可直接展示给用户的错误信息")
    request_id: str | None = Field(default=None, description="请求追踪 ID")
    error_id: str | None = Field(default=None, description="服务端内部错误 ID")
    details: list[ErrorDetail] | None = Field(default=None, description="字段级校验错误")


OPENAPI_ERROR_RESPONSES = {
    "default": {
        "model": ErrorResponse,
        "description": "统一错误响应",
    },
}


class ApiError(Exception):
    def __init__(
        self,
        *,
        status_code: int,
        code: str,
        message: str,
        headers: dict[str, str] | None = None,
        details: list[ErrorDetail] | None = None,
    ) -> None:
        super().__init__(message)
        self.status_code = status_code
        self.code = code
        self.message = message
        self.headers = headers or {}
        self.details = details


class BadRequestError(ApiError):
    def __init__(self, message: str, *, code: str = "bad_request") -> None:
        super().__init__(status_code=400, code=code, message=message)


class NotFoundError(ApiError):
    def __init__(self, message: str, *, code: str = "not_found") -> None:
        super().__init__(status_code=404, code=code, message=message)


class ConflictError(ApiError):
    def __init__(self, message: str, *, code: str = "conflict") -> None:
        super().__init__(status_code=409, code=code, message=message)


_STATUS_CODES = {
    400: "bad_request",
    401: "unauthorized",
    403: "forbidden",
    404: "not_found",
    409: "conflict",
    422: "unprocessable_entity",
    429: "rate_limited",
    500: "internal_error",
    502: "upstream_error",
    503: "service_unavailable",
}

_STATUS_MESSAGES = {
    400: "请求无效",
    401: "未登录或登录已过期",
    403: "无权执行该操作",
    404: "请求的资源不存在",
    409: "当前资源状态冲突",
    422: "请求参数校验失败",
    429: "请求过于频繁",
    500: "服务器内部错误，请稍后重试",
    502: "上游服务暂时不可用",
    503: "服务暂时不可用",
}


def _request_id(request: Request) -> str | None:
    return getattr(getattr(request, "state", None), "request_id", None)


def _header(headers: dict[str, str] | None, name: str) -> str | None:
    if not headers:
        return None
    return next((value for key, value in headers.items() if key.lower() == name.lower()), None)


def _response(
    request: Request,
    *,
    status_code: int,
    code: str,
    message: str,
    headers: dict[str, str] | None = None,
    error_id: str | None = None,
    details: list[ErrorDetail] | None = None,
) -> JSONResponse:
    payload = ErrorResponse(
        code=code,
        message=message,
        request_id=_request_id(request),
        error_id=error_id,
        details=details,
    )
    return JSONResponse(
        status_code=status_code,
        content=payload.model_dump(exclude_none=True),
        headers=headers,
    )


async def api_error_handler(request: Request, exc: ApiError) -> JSONResponse:
    return _response(
        request,
        status_code=exc.status_code,
        code=exc.code,
        message=exc.message,
        headers=exc.headers,
        error_id=_header(exc.headers, "X-Error-ID"),
        details=exc.details,
    )


async def application_error_handler(request: Request, exc: ApplicationError) -> JSONResponse:
    status_code = 500
    if isinstance(exc, InvalidRequestError):
        status_code = 400
    elif isinstance(exc, ResourceNotFoundError):
        status_code = 404
    elif isinstance(exc, ResourceConflictError):
        status_code = 409
    elif isinstance(exc, UpstreamUnavailableError):
        status_code = 503
    return _response(
        request,
        status_code=status_code,
        code=exc.code,
        message=exc.message,
    )


async def http_exception_handler(request: Request, exc: StarletteHTTPException) -> JSONResponse:
    status_code = exc.status_code
    message = exc.detail if isinstance(exc.detail, str) else _STATUS_MESSAGES.get(status_code, "请求失败")
    return _response(
        request,
        status_code=status_code,
        code=_STATUS_CODES.get(status_code, "http_error"),
        message=message,
        headers=exc.headers,
        error_id=_header(exc.headers, "X-Error-ID"),
    )


async def validation_error_handler(request: Request, exc: RequestValidationError) -> JSONResponse:
    details = [
        ErrorDetail(
            path=".".join(str(part) for part in error.get("loc", ())),
            message=str(error.get("msg", "请求参数无效")),
            type=str(error.get("type", "validation_error")),
        )
        for error in exc.errors()
    ]
    return _response(
        request,
        status_code=422,
        code="validation_error",
        message="请求参数校验失败",
        details=details,
    )


async def value_error_handler(request: Request, exc: ValueError) -> JSONResponse:
    error_id, message = build_internal_error("请求参数无效")
    logger.warning(
        "请求参数处理失败 error_id=%s: %s %s error_type=%s",
        error_id,
        request.method,
        request.url.path,
        type(exc).__name__,
    )
    return _response(
        request,
        status_code=400,
        code="bad_request",
        message=message,
        headers={"X-Error-ID": error_id},
        error_id=error_id,
    )


async def lookup_error_handler(request: Request, exc: LookupError) -> JSONResponse:
    return _response(
        request,
        status_code=404,
        code="not_found",
        message=str(exc) or "请求的资源不存在",
    )


async def global_exception_handler(request: Request, exc: Exception) -> JSONResponse:
    error_id, message = build_internal_error("服务器内部错误，请稍后重试")
    logger.error(
        "未捕获异常 error_id=%s: %s %s error=%s",
        error_id,
        request.method,
        request.url.path,
        exc,
        exc_info=True,
    )
    return _response(
        request,
        status_code=500,
        code="internal_error",
        message=message,
        headers={"X-Error-ID": error_id},
        error_id=error_id,
    )


def register_error_handlers(application: FastAPI) -> None:
    application.add_exception_handler(ApiError, api_error_handler)
    application.add_exception_handler(ApplicationError, application_error_handler)
    application.add_exception_handler(StarletteHTTPException, http_exception_handler)
    application.add_exception_handler(RequestValidationError, validation_error_handler)
    application.add_exception_handler(ValueError, value_error_handler)
    application.add_exception_handler(LookupError, lookup_error_handler)
    application.add_exception_handler(Exception, global_exception_handler)
