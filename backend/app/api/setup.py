from __future__ import annotations

from collections.abc import Awaitable, Callable
from typing import Any

from fastapi import FastAPI
from fastapi.responses import JSONResponse

from app.api import errors, system
from app.api.router import create_api_router


def register_api(
    application: FastAPI,
    *,
    active_user_dependencies: list[Any],
    readiness_handler: Callable[[], Awaitable[JSONResponse]],
    health_handler: Callable[[], Awaitable[JSONResponse]],
    metrics_access_dependency: Callable,
) -> None:
    errors.register_error_handlers(application)
    application.include_router(
        create_api_router(active_user_dependencies=active_user_dependencies),
    )
    system.register_system_endpoints(
        application,
        readiness_handler=readiness_handler,
        health_handler=health_handler,
        metrics_access_dependency=metrics_access_dependency,
    )
