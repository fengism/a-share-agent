"""健康检查与运行态 API 端点。"""

from __future__ import annotations

from collections.abc import Awaitable, Callable

from fastapi import Depends, FastAPI
from fastapi.responses import JSONResponse

from app.api.schemas import HealthMetricsResponse, LivenessResponse, ReadinessResponse


async def liveness() -> LivenessResponse:
    return LivenessResponse(status="ok")


async def health_metrics() -> HealthMetricsResponse:
    from app.core.cache import cache
    from app.core.metrics import metrics
    from app.infrastructure.providers.provider_gateway import provider_gateway

    return HealthMetricsResponse(
        status="ok",
        metrics=metrics.snapshot(),
        global_cache=cache.snapshot(),
        provider_circuits=provider_gateway.snapshot(),
    )


def register_system_endpoints(
    application: FastAPI,
    *,
    readiness_handler: Callable[[], Awaitable[JSONResponse]],
    health_handler: Callable[[], Awaitable[JSONResponse]],
    metrics_access_dependency: Callable,
) -> None:
    application.add_api_route(
        "/api/health/live",
        liveness,
        methods=["GET"],
        response_model=LivenessResponse,
    )
    application.add_api_route(
        "/api/health/ready",
        readiness_handler,
        methods=["GET"],
        response_model=ReadinessResponse,
    )
    application.add_api_route(
        "/api/health",
        health_handler,
        methods=["GET"],
        response_model=ReadinessResponse,
    )
    application.add_api_route(
        "/api/health/metrics",
        health_metrics,
        methods=["GET"],
        dependencies=[Depends(metrics_access_dependency)],
        response_model=HealthMetricsResponse,
    )
