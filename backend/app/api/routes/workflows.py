"""Authenticated durable Workflow lifecycle endpoints."""

from __future__ import annotations

from typing import Annotated

from fastapi import APIRouter, Body, Depends, Header, Path, status
from sse_starlette.sse import EventSourceResponse

from app.api.auth.dependencies import require_active_user
from app.api.errors import BadRequestError, NotFoundError, TooManyRequestsError
from app.api.schemas import WorkflowJobResponse, WorkflowSubmissionResponse
from app.api.streaming import SSE_RESPONSES
from app.domain.identity import AuthenticatedUser
from app.modules.daily_review.public import DailyReviewRequest
from app.modules.industry_chain.public import IndustryChainResearchScope
from app.modules.screener.public import ScreenerStrategyRequest, validate_screener_strategy_request
from app.modules.workflow.public import (
    WorkflowCapacityError,
    WorkflowJobSnapshot,
    WorkflowSubmissionSnapshot,
    cancel_workflow,
    create_workflow_event_generator,
    get_workflow,
    submit_analysis_workflow,
    submit_daily_review_workflow,
    submit_industry_chain_workflow,
    submit_screener_strategy_workflow,
)

router = APIRouter()


def _job_response(job: WorkflowJobSnapshot) -> WorkflowJobResponse:
    return WorkflowJobResponse(
        id=job.id,
        kind=job.kind,
        dedupe_key=job.dedupe_key,
        status=job.status,
        attempts=job.attempts,
        max_attempts=job.max_attempts,
        last_error=job.last_error,
        created_at=job.created_at,
        updated_at=job.updated_at,
        completed_at=job.completed_at,
    )


def _submission_response(submission: WorkflowSubmissionSnapshot) -> WorkflowSubmissionResponse:
    return WorkflowSubmissionResponse(
        job=_job_response(submission.job),
        attached=submission.attached,
    )


def _capacity_error(error: WorkflowCapacityError) -> TooManyRequestsError:
    return TooManyRequestsError(
        "任务队列已满，请等待已有任务完成",
        code=f"workflow.{error.scope}_capacity_reached",
        retry_after_seconds=30,
    )


@router.post(
    "/analysis/{code}",
    response_model=WorkflowSubmissionResponse,
    status_code=status.HTTP_202_ACCEPTED,
)
async def submit_analysis_job(
    code: Annotated[str, Path(pattern=r"^\d{6}$")],
    user: AuthenticatedUser = Depends(require_active_user),
) -> WorkflowSubmissionResponse:
    try:
        return _submission_response(await submit_analysis_workflow(code, user["id"]))
    except WorkflowCapacityError as error:
        raise _capacity_error(error) from error


@router.post(
    "/daily-review",
    response_model=WorkflowSubmissionResponse,
    status_code=status.HTTP_202_ACCEPTED,
)
async def submit_daily_review_job(
    request: DailyReviewRequest,
    user: AuthenticatedUser = Depends(require_active_user),
) -> WorkflowSubmissionResponse:
    try:
        return _submission_response(
            await submit_daily_review_workflow(request.model_dump(mode="json"), user["id"])
        )
    except WorkflowCapacityError as error:
        raise _capacity_error(error) from error


@router.post(
    "/industry-chain/{name}",
    response_model=WorkflowSubmissionResponse,
    status_code=status.HTTP_202_ACCEPTED,
)
async def submit_industry_chain_job(
    name: Annotated[str, Path(min_length=1, max_length=100)],
    user: AuthenticatedUser = Depends(require_active_user),
    scope: Annotated[IndustryChainResearchScope | None, Body()] = None,
) -> WorkflowSubmissionResponse:
    try:
        return _submission_response(await submit_industry_chain_workflow(name.strip(), user["id"], scope))
    except ValueError as error:
        raise BadRequestError(str(error), code="industry_chain.invalid_scope") from error
    except WorkflowCapacityError as error:
        raise _capacity_error(error) from error


@router.post(
    "/screener-strategy",
    response_model=WorkflowSubmissionResponse,
    status_code=status.HTTP_202_ACCEPTED,
)
async def submit_screener_strategy_job(
    request: ScreenerStrategyRequest,
    user: AuthenticatedUser = Depends(require_active_user),
) -> WorkflowSubmissionResponse:
    try:
        validate_screener_strategy_request(request)
        return _submission_response(await submit_screener_strategy_workflow(request.model_dump(mode="json"), user["id"]))
    except ValueError as error:
        raise BadRequestError(str(error), code="screener.invalid_strategy") from error
    except WorkflowCapacityError as error:
        raise _capacity_error(error) from error


@router.get("/{job_id}", response_model=WorkflowJobResponse)
async def get_workflow_job(
    job_id: str,
    user: AuthenticatedUser = Depends(require_active_user),
) -> WorkflowJobResponse:
    job = await get_workflow(job_id, user["id"])
    if job is None:
        raise NotFoundError("任务不存在", code="workflow.not_found")
    return _job_response(job)


@router.get(
    "/{job_id}/stream",
    response_class=EventSourceResponse,
    responses=SSE_RESPONSES,
)
async def stream_workflow_job(
    job_id: str,
    last_event_id: Annotated[str | None, Header(alias="Last-Event-ID")] = None,
    user: AuthenticatedUser = Depends(require_active_user),
):
    event_generator = await create_workflow_event_generator(
        job_id,
        user["id"],
        last_event_id=last_event_id,
    )
    if event_generator is None:
        raise NotFoundError("任务不存在", code="workflow.not_found")
    return EventSourceResponse(event_generator)


@router.delete("/{job_id}", response_model=WorkflowJobResponse)
async def cancel_workflow_job(
    job_id: str,
    user: AuthenticatedUser = Depends(require_active_user),
) -> WorkflowJobResponse:
    job = await cancel_workflow(job_id, user["id"])
    if job is None:
        raise NotFoundError("任务不存在", code="workflow.not_found")
    return _job_response(job)
