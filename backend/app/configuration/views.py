"""从平铺 Settings 派生的只读配置分组。"""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from app.configuration.schema import Settings


@dataclass(frozen=True, slots=True)
class LLMSettingsView:
    provider: str
    api_mode: str
    api_version: str
    api_key: str
    base_url: str
    model: str
    temperature: float
    timeout_seconds: int

    @classmethod
    def from_settings(cls, settings: Settings) -> LLMSettingsView:
        return cls(
            provider=settings.llm_provider,
            api_mode=settings.llm_api_mode,
            api_version=settings.llm_api_version,
            api_key=settings.llm_api_key,
            base_url=settings.llm_base_url,
            model=settings.llm_model,
            temperature=settings.llm_temperature,
            timeout_seconds=settings.llm_timeout_seconds,
        )


@dataclass(frozen=True, slots=True)
class ProviderSettingsView:
    gateway_max_attempts: int
    failure_threshold: int
    circuit_open_seconds: float
    retry_base_seconds: float
    retry_budget_seconds: float
    retry_jitter_seconds: float
    tdxhub_timeout_seconds: float
    eastmoney_min_interval_seconds: float
    eastmoney_datacenter_min_interval_seconds: float

    @classmethod
    def from_settings(cls, settings: Settings) -> ProviderSettingsView:
        return cls(
            gateway_max_attempts=settings.provider_gateway_max_attempts,
            failure_threshold=settings.provider_failure_threshold,
            circuit_open_seconds=settings.provider_circuit_open_seconds,
            retry_base_seconds=settings.provider_retry_base_seconds,
            retry_budget_seconds=settings.provider_retry_budget_seconds,
            retry_jitter_seconds=settings.provider_retry_jitter_seconds,
            tdxhub_timeout_seconds=settings.tdxhub_timeout_seconds,
            eastmoney_min_interval_seconds=settings.eastmoney_min_interval_seconds,
            eastmoney_datacenter_min_interval_seconds=(
                settings.eastmoney_datacenter_min_interval_seconds
            ),
        )


@dataclass(frozen=True, slots=True)
class RuntimeSettingsView:
    app_data_dir: Path
    cache_ttl_analysis: int
    blocking_thread_pool_workers: int
    max_concurrent_chat_per_user: int
    max_concurrent_chat_total: int
    max_concurrent_llm_requests: int
    chat_total_timeout_seconds: int
    chat_heartbeat_seconds: int
    chat_tool_timeout_seconds: int
    chat_max_tool_calls_per_round: int
    chat_max_tool_calls_total: int
    chat_max_tool_context_characters: int
    chat_max_synthesis_characters: int
    database_backup_enabled: bool
    database_backup_interval_seconds: int
    database_backup_retention_count: int
    database_backup_dir: Path | None
    database_backup_mirror_dir: Path | None

    @classmethod
    def from_settings(cls, settings: Settings) -> RuntimeSettingsView:
        return cls(
            app_data_dir=settings.app_data_dir,
            cache_ttl_analysis=settings.cache_ttl_analysis,
            blocking_thread_pool_workers=settings.blocking_thread_pool_workers,
            max_concurrent_chat_per_user=settings.max_concurrent_chat_per_user,
            max_concurrent_chat_total=settings.max_concurrent_chat_total,
            max_concurrent_llm_requests=settings.max_concurrent_llm_requests,
            chat_total_timeout_seconds=settings.chat_total_timeout_seconds,
            chat_heartbeat_seconds=settings.chat_heartbeat_seconds,
            chat_tool_timeout_seconds=settings.chat_tool_timeout_seconds,
            chat_max_tool_calls_per_round=settings.chat_max_tool_calls_per_round,
            chat_max_tool_calls_total=settings.chat_max_tool_calls_total,
            chat_max_tool_context_characters=settings.chat_max_tool_context_characters,
            chat_max_synthesis_characters=settings.chat_max_synthesis_characters,
            database_backup_enabled=settings.database_backup_enabled,
            database_backup_interval_seconds=settings.database_backup_interval_seconds,
            database_backup_retention_count=settings.database_backup_retention_count,
            database_backup_dir=settings.database_backup_dir,
            database_backup_mirror_dir=settings.database_backup_mirror_dir,
        )


@dataclass(frozen=True, slots=True)
class IntegrationSettingsView:
    notion_enabled: bool
    notion_api_token: str
    feishu_enabled: bool
    feishu_app_id: str
    feishu_app_secret: str
    iwencai_enabled: bool
    iwencai_base_url: str
    iwencai_api_key: str
    twitter_feeds: tuple[str, ...]

    @classmethod
    def from_settings(cls, settings: Settings) -> IntegrationSettingsView:
        return cls(
            notion_enabled=settings.notion_enabled,
            notion_api_token=settings.notion_api_token,
            feishu_enabled=settings.feishu_enabled,
            feishu_app_id=settings.feishu_app_id,
            feishu_app_secret=settings.feishu_app_secret,
            iwencai_enabled=settings.iwencai_enabled,
            iwencai_base_url=settings.iwencai_base_url,
            iwencai_api_key=settings.iwencai_api_key,
            twitter_feeds=tuple(settings.twitter_feeds),
        )


@dataclass(frozen=True, slots=True)
class WorkerSettingsView:
    background_task_jitter_seconds: float
    background_task_lease_seconds: float
    background_task_standby_poll_seconds: float
    background_task_readiness_failure_threshold: int
    workflow_job_poll_seconds: float
    workflow_job_lease_seconds: int
    workflow_job_max_attempts: int
    workflow_job_retry_base_seconds: float
    workflow_job_worker_concurrency: int
    workflow_job_max_running_per_user: int
    workflow_job_max_active_per_user: int
    workflow_job_max_active_total: int
    workflow_job_retention_seconds: int
    bot_enabled: bool
    bot_job_poll_seconds: float
    bot_job_lease_seconds: int
    bot_job_max_attempts: int
    bot_job_retry_base_seconds: float
    bot_job_worker_concurrency: int

    @classmethod
    def from_settings(cls, settings: Settings) -> WorkerSettingsView:
        return cls(
            background_task_jitter_seconds=settings.background_task_jitter_seconds,
            background_task_lease_seconds=settings.background_task_lease_seconds,
            background_task_standby_poll_seconds=settings.background_task_standby_poll_seconds,
            background_task_readiness_failure_threshold=(
                settings.background_task_readiness_failure_threshold
            ),
            workflow_job_poll_seconds=settings.workflow_job_poll_seconds,
            workflow_job_lease_seconds=settings.workflow_job_lease_seconds,
            workflow_job_max_attempts=settings.workflow_job_max_attempts,
            workflow_job_retry_base_seconds=settings.workflow_job_retry_base_seconds,
            workflow_job_worker_concurrency=settings.workflow_job_worker_concurrency,
            workflow_job_max_running_per_user=settings.workflow_job_max_running_per_user,
            workflow_job_max_active_per_user=settings.workflow_job_max_active_per_user,
            workflow_job_max_active_total=settings.workflow_job_max_active_total,
            workflow_job_retention_seconds=settings.workflow_job_retention_seconds,
            bot_enabled=settings.bot_enabled,
            bot_job_poll_seconds=settings.bot_job_poll_seconds,
            bot_job_lease_seconds=settings.bot_job_lease_seconds,
            bot_job_max_attempts=settings.bot_job_max_attempts,
            bot_job_retry_base_seconds=settings.bot_job_retry_base_seconds,
            bot_job_worker_concurrency=settings.bot_job_worker_concurrency,
        )


__all__ = [
    "IntegrationSettingsView",
    "LLMSettingsView",
    "ProviderSettingsView",
    "RuntimeSettingsView",
    "WorkerSettingsView",
]
