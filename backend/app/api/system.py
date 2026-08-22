"""健康检查与运行态 API 端点。"""

from __future__ import annotations

from collections.abc import Awaitable, Callable, Mapping

from fastapi import Depends, FastAPI
from fastapi.responses import JSONResponse, PlainTextResponse

from app.api.schemas import (
    HealthMetricsResponse,
    LivenessResponse,
    ProviderCircuitStateResponse,
    ReadinessResponse,
)
from app.core.operational import OperationalSnapshot

OperationalSnapshotProvider = Callable[[], Awaitable[OperationalSnapshot]]


async def liveness() -> LivenessResponse:
    return LivenessResponse(status="ok")


async def health_metrics(
    operational_snapshot_provider: OperationalSnapshotProvider,
) -> HealthMetricsResponse:
    snapshot = await operational_snapshot_provider()
    metrics_snapshot = dict(snapshot.metrics)
    workflow_snapshot = metrics_snapshot.get("workflow")
    workflow_metrics = dict(workflow_snapshot) if isinstance(workflow_snapshot, Mapping) else {}
    workflow_metrics["queue"] = dict(snapshot.workflow_queue)
    metrics_snapshot["workflow"] = workflow_metrics
    metrics_snapshot["runtime"] = {
        "background_tasks": snapshot.background_tasks,
        "backups": snapshot.backups,
    }

    return HealthMetricsResponse(
        status="ok",
        metrics=metrics_snapshot,
        global_cache=dict(snapshot.global_cache),
        provider_circuits={
            name: ProviderCircuitStateResponse.model_validate(circuit)
            for name, circuit in snapshot.provider_circuits.items()
        },
    )


async def prometheus_metrics(
    operational_snapshot_provider: OperationalSnapshotProvider,
) -> PlainTextResponse:
    from app.core.prometheus import render_prometheus_metrics

    snapshot = await operational_snapshot_provider()
    content = render_prometheus_metrics(
        snapshot.metrics,
        background_tasks=snapshot.background_tasks,
        workflow_queue=snapshot.workflow_queue,
        backups=snapshot.backups,
    )
    return PlainTextResponse(content, media_type="text/plain; version=0.0.4; charset=utf-8")


def register_system_endpoints(
    application: FastAPI,
    *,
    readiness_handler: Callable[[], Awaitable[JSONResponse]],
    health_handler: Callable[[], Awaitable[JSONResponse]],
    metrics_access_dependency: Callable,
    operational_snapshot_provider: OperationalSnapshotProvider,
) -> None:
    async def health_metrics_endpoint() -> HealthMetricsResponse:
        return await health_metrics(operational_snapshot_provider)

    async def prometheus_metrics_endpoint() -> PlainTextResponse:
        return await prometheus_metrics(operational_snapshot_provider)

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
        health_metrics_endpoint,
        methods=["GET"],
        name="health_metrics",
        dependencies=[Depends(metrics_access_dependency)],
        response_model=HealthMetricsResponse,
    )
    application.add_api_route(
        "/api/health/metrics/prometheus",
        prometheus_metrics_endpoint,
        methods=["GET"],
        name="prometheus_metrics",
        dependencies=[Depends(metrics_access_dependency)],
        response_class=PlainTextResponse,
    )
