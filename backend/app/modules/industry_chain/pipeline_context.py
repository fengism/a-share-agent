"""产业链投研管道上下文对象定义。

在各个 Pipeline 阶段之间封装并传递状态，消除单体函数中长跨度局部变量传递问题。
"""

from __future__ import annotations

import asyncio
import logging
import time
from collections.abc import Awaitable, Callable
from dataclasses import dataclass, field
from typing import Any, Literal

from app.agentic.events import AgentEvent, auditable_agent_event
from app.agentic.public import AgentEvidence
from app.configuration import Settings
from app.core.cache import analysis_cache as cache
from app.core.progress import ProgressEmitter
from app.domain.industry_chain import IndustryChainResearchScope
from app.modules.industry_chain.events import IndustryChainProgress
from app.modules.industry_chain.models import (
    IndustryChainEvidenceStats,
    IndustryChainResult,
)

logger = logging.getLogger(__name__)


@dataclass
class PipelineContext:
    """产业链分析管道运行时上下文。"""

    name: str
    user_id: int
    resolved_scope: IndustryChainResearchScope
    settings: Settings
    progress: ProgressEmitter
    before_persist: Callable[[], Awaitable[None]] | None = None
    total_started_at: float = field(default_factory=time.perf_counter)

    # 阶段时间戳
    research_started_at: float = 0.0
    draft_started_at: float = 0.0
    verification_started_at: float = 0.0
    finalization_started_at: float = 0.0
    archive_started_at: float = 0.0
    synthesis_started_at: float = 0.0

    # 阶段耗时统计（毫秒）
    research_duration_ms: int = 0
    draft_duration_ms: int = 0
    verification_duration_ms: int = 0
    finalization_duration_ms: int = 0
    archive_duration_ms: int = 0
    synthesis_duration_ms: int = 0

    # 调研阶段数据
    atlas_chain: Any = None
    atlas_prior: str = ""
    expected_segments: tuple[str, ...] = ()
    research_outcome: Any = None
    public_data: dict[str, Any] = field(default_factory=dict)
    collection_metadata: dict[str, Any] = field(default_factory=dict)
    warnings: list[str] = field(default_factory=list)
    fallback_research: bool = False
    all_evidence: list[AgentEvidence] = field(default_factory=list)
    evidence_catalog: list[Any] = field(default_factory=list)
    evidence_stats: IndustryChainEvidenceStats = field(default_factory=IndustryChainEvidenceStats)

    # 初稿阶段数据
    prompt_context: dict[str, Any] = field(default_factory=dict)
    structured_prompt_succeeded: bool = False
    result: IndustryChainResult | None = None

    def make_event(
        self,
        *,
        event_type: Literal["stage_started", "stage_completed", "stage_failed", "agent_event", "complete", "error"],
        stage: str,
        message: str,
        result: IndustryChainResult | None = None,
        agent_event=None,
    ) -> IndustryChainProgress:
        """构造管道进度事件。"""
        res = result if result is not None else self.result
        return IndustryChainProgress(
            type=event_type,
            stage=stage,
            message=message,
            result=res,
            agent_event=agent_event,
            archive_id=res.archive_id if res is not None else "",
            archive_status=res.archive_status if res is not None else "none",
            quality_status=res.quality_status if res is not None else "complete",
            warnings=list(res.warnings) if res is not None else list(self.warnings),
        )

    async def emit_agent_event(self, event: AgentEvent) -> None:
        """发送审计后的 Agent 事件。"""
        public_event = auditable_agent_event(event)
        if public_event is None:
            return
        await self.progress.emit(
            self.make_event(
                event_type="agent_event",
                stage="research",
                message="",
                agent_event=public_event,
            )
        )

    async def check_cancellation(self) -> None:
        """协作式检查任务是否已取消或外部状态失效。"""
        current_task = asyncio.current_task()
        if current_task is not None and current_task.cancelling():
            raise asyncio.CancelledError(f"产业链分析任务已取消: {self.name}")
        if self.before_persist is not None:
            await self.before_persist()

    def save_checkpoint(self, stage_name: str) -> None:
        """将当前阶段分析成果保存为轻量检查点。"""
        if self.result is None:
            return
        checkpoint_key = f"industry_chain_checkpoint:{self.user_id}:{self.name}:{stage_name}"
        try:
            cache.set(
                checkpoint_key,
                {
                    "result": self.result.model_dump(),
                    "warnings": self.warnings,
                    "evidence_stats": self.evidence_stats.model_dump(),
                },
                ttl=1800,
            )
        except Exception as exc:
            logger.debug("保存检查点失败 (%s): %s", stage_name, exc)

    def load_checkpoint(self, stage_name: str) -> bool:
        """从阶段检查点恢复数据。"""
        checkpoint_key = f"industry_chain_checkpoint:{self.user_id}:{self.name}:{stage_name}"
        data = cache.get(checkpoint_key)
        if not data or not isinstance(data, dict):
            return False
        try:
            raw_result = data.get("result")
            if raw_result:
                self.result = IndustryChainResult.model_validate(raw_result)
                self.warnings = list(data.get("warnings", []))
                if "evidence_stats" in data:
                    self.evidence_stats = IndustryChainEvidenceStats.model_validate(data["evidence_stats"])
                return True
        except Exception as exc:
            logger.debug("恢复检查点失败 (%s): %s", stage_name, exc)
        return False
