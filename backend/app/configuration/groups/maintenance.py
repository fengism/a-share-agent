"""后台任务、行情归档与备份策略配置分组。"""

from __future__ import annotations

from pathlib import Path

from pydantic import Field

from app.configuration.groups.base import ConfigGroup


class MaintenanceGroup(ConfigGroup):
    """常驻后台任务、持久化任务队列、行情归档与数据库备份。"""

    PREFIX = ""

    background_task_jitter_seconds: float = 15.0
    background_task_lease_seconds: float = 60.0
    background_task_standby_poll_seconds: float = 10.0
    background_task_readiness_failure_threshold: int = Field(default=3, ge=1, le=100)
    market_daily_bar_refresh_enabled: bool = True
    market_daily_bar_refresh_poll_seconds: int = Field(default=60, ge=15, le=3600)
    market_daily_bar_refresh_retry_base_seconds: int = Field(default=60, ge=1, le=1800)
    market_daily_observation_retention_days: int = Field(default=1095, ge=7, le=3650)
    market_daily_attempt_retention_days: int = Field(default=1095, ge=30, le=3650)
    potential_retention_days: int = Field(default=180, ge=7, le=3650)
    valuation_snapshot_retention_days: int = Field(default=30, ge=7, le=3650)
    analysis_archive_retention_days: int = Field(default=90, ge=7, le=3650)
    industry_chain_retention_days: int = Field(default=180, ge=7, le=3650)
    # 管理员操作审计（admin_audit_logs）保留天数；0 = 永久保留
    admin_audit_retention_days: int = Field(default=365, ge=0, le=3650)
    # 登录审计（login_audit_logs）保留天数；公网实例会持续记录失败登录，必须有上限
    login_audit_retention_days: int = Field(default=180, ge=0, le=3650)
    # 常驻后台任务开关，默认全部关闭，支持在前端按需开启
    macro_analysis_prewarm_enabled: bool = False
    daily_review_prewarm_enabled: bool = False
    potential_stock_daily_enabled: bool = False
    stock_valuation_snapshot_refresh_enabled: bool = False
    workflow_job_poll_seconds: float = Field(default=0.5, gt=0)
    workflow_job_lease_seconds: int = Field(default=900, ge=30)
    workflow_job_max_attempts: int = Field(default=2, ge=1, le=5)
    workflow_job_retry_base_seconds: float = Field(default=5.0, ge=0)
    workflow_job_worker_concurrency: int = Field(default=2, ge=1, le=8)
    workflow_job_max_running_per_user: int = Field(default=1, ge=1, le=8)
    workflow_job_max_active_per_user: int = Field(default=10, ge=1, le=1000)
    workflow_job_max_active_total: int = Field(default=100, ge=1, le=10000)
    workflow_job_retention_seconds: int = Field(default=30 * 24 * 60 * 60, ge=3600)
    database_backup_enabled: bool = True
    database_backup_interval_seconds: int = Field(default=24 * 60 * 60, ge=300)
    database_backup_retention_count: int = Field(default=3, ge=1, le=90)
    database_backup_include_market_daily: bool = True
    market_daily_backup_interval_days: int = Field(default=7, ge=1, le=90)
    market_daily_backup_compression_level: int = Field(default=1, ge=1, le=9)
    database_backup_dir: Path | None = None
    database_backup_mirror_dir: Path | None = None
