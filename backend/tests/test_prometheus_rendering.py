"""Prometheus 文本渲染：转义、数值规范化、各分区字段。

这份渲染此前完全没有测试（覆盖率 0%），而它的失败方式是"静默"的：标签里漏个引号、
``nan`` 直接写进文本，Prometheus 只会拒收整个抓取或让指标消失，日志里什么都没有。
"""

from __future__ import annotations

import math

from app.core.prometheus import _escape_label, _metric_name, _sample, render_prometheus_metrics


def _render(snapshot: dict | None = None, **kwargs) -> str:
    return render_prometheus_metrics(
        snapshot or {},
        background_tasks=kwargs.get("background_tasks", {}),
        workflow_queue=kwargs.get("workflow_queue", {}),
        backups=kwargs.get("backups", {}),
    )


def test_label_escaping_handles_backslash_quote_and_newline() -> None:
    assert _escape_label('a"b') == 'a\\"b'
    assert _escape_label("a\\b") == "a\\\\b"
    assert _escape_label("a\nb") == "a\\nb"


def test_metric_name_is_sanitized() -> None:
    assert _metric_name("a_share-foo.bar") == "a_share_foo_bar"
    assert _metric_name("keep:colons") == "keep:colons"


def test_sample_renders_bool_as_one_zero() -> None:
    assert _sample("x", True) == "x 1"
    assert _sample("x", False) == "x 0"


def test_sample_renders_non_finite_as_zero() -> None:
    # 直接写 "nan"/"inf" 会让 Prometheus 拒收整个抓取。
    assert _sample("x", float("nan")) == "x 0"
    assert _sample("x", float("inf")) == "x 0"
    assert _sample("x", -math.inf) == "x 0"


def test_sample_labels_are_sorted_and_escaped() -> None:
    rendered = _sample("x", 3, b='v"1', a="v2")
    assert rendered == 'x{a="v2",b="v\\"1"} 3'


def test_empty_snapshot_still_emits_type_header_and_trailing_newline() -> None:
    text = _render()
    assert text.startswith("# TYPE a_share_http_requests_total counter")
    assert text.endswith("\n")
    # 全局队列指标即便为空也要给出 0，否则看板会画不出线
    assert "a_share_workflow_queue_jobs{status=\"pending\"} 0" in text
    assert "a_share_workflow_queue_jobs{status=\"running\"} 0" in text


def test_http_requests_section_renders_three_series() -> None:
    text = _render(
        {
            "requests": [
                {
                    "method": "GET",
                    "path": "/api/stock/600519",
                    "status": 200,
                    "count": 5,
                    "duration_ms_avg": 12.5,
                    "duration_ms_max": 30,
                }
            ]
        }
    )
    assert 'a_share_http_requests_total{method="GET",path="/api/stock/600519",status="200"} 5' in text
    assert "a_share_http_request_duration_milliseconds_avg" in text
    assert "a_share_http_request_duration_milliseconds_max" in text


def test_provider_and_llm_sections_use_configurable_labels() -> None:
    text = _render(
        {
            "providers": {"eastmoney": {"attempts": 3, "successes": 2, "failures": 1}},
            "llm": {
                "prompts": {
                    "daily_review": {
                        "glm-4": {
                            "attempts": 1,
                            "successes": 1,
                            "prompt_tokens": 100,
                            "ttft_ms_avg": 250.0,
                        }
                    }
                }
            },
        }
    )
    assert 'a_share_provider_attempts_total{provider="eastmoney"} 3' in text
    assert 'a_share_provider_fallback_attempts_total{provider="eastmoney"} 0' in text
    assert (
        'a_share_llm_prompt_tokens_total{model="glm-4",prompt="daily_review"} 100' in text
    )
    assert 'a_share_llm_ttft_ms_avg{model="glm-4",prompt="daily_review"} 250' in text


def test_workflow_queue_and_background_tasks() -> None:
    text = _render(
        workflow_queue={"pending": 2, "running": 1, "oldest_age_seconds": 42.5},
        background_tasks={
            "daily_refresh": {
                "restart_count": 3,
                "consecutive_errors": 1,
                "unexpected_exit": True,
            }
        },
    )
    assert 'a_share_workflow_queue_jobs{status="pending"} 2' in text
    assert 'a_share_workflow_queue_jobs{status="running"} 1' in text
    assert "a_share_workflow_queue_oldest_age_seconds 42.5" in text
    assert 'a_share_background_task_restarts_total{task="daily_refresh"} 3' in text
    assert 'a_share_background_task_unexpected_exit{task="daily_refresh"} 1' in text


def test_backup_age_is_omitted_when_unknown() -> None:
    text = _render(
        backups={"main": {"exists": True, "checksum_exists": False, "age_seconds": None}}
    )
    assert 'a_share_database_backup_exists{database="main"} 1' in text
    assert 'a_share_database_backup_checksum_exists{database="main"} 0' in text
    # 缺失的备份年龄不能写成 0（会被误读成"刚刚备份过"）
    assert "a_share_database_backup_age_seconds" not in text


def test_persistence_operations_and_history_indexes() -> None:
    text = _render(
        {
            "persistence": {
                "databases": {"main": {"file_bytes": 4096, "freelist_ratio": 0.25}},
                "operations": {"main": {"write": {"attempts": 7, "busy_failures": 2}}},
                "history_indexes": {"daily_review": {"ready": True, "dirty": False}},
            }
        }
    )
    assert 'a_share_database_file_bytes{database="main"} 4096' in text
    assert 'a_share_database_freelist_ratio{database="main"} 0.25' in text
    assert (
        'a_share_persistence_operation_attempts_total{database="main",operation="write"} 7'
    ) in text
    assert (
        'a_share_persistence_operation_busy_failures_total{database="main",operation="write"} 2'
    ) in text
    assert 'a_share_history_index_ready{kind="daily_review"} 1' in text


def test_provider_operations_are_exported_with_operation_label() -> None:
    """降级失败只出现在 operation 维度，必须导出才可告警。"""
    text = _render(
        {
            "provider_operations": {
                "llm_chat": {
                    "fallback_unavailable": {
                        "attempts": 2, "failures": 2, "fallback_attempts": 2,
                    },
                    "fallback_incompatible": {
                        "attempts": 1, "failures": 1, "fallback_attempts": 1,
                    },
                    "fallback_to_model": {
                        "attempts": 5, "successes": 5, "fallback_attempts": 5,
                    },
                }
            }
        }
    )
    assert (
        'a_share_provider_operation_fallback_attempts_total'
        '{operation="fallback_unavailable",provider="llm_chat"} 2' in text
    )
    assert (
        'a_share_provider_operation_failures_total'
        '{operation="fallback_incompatible",provider="llm_chat"} 1' in text
    )
    assert (
        'a_share_provider_operation_successes_total'
        '{operation="fallback_to_model",provider="llm_chat"} 5' in text
    )
    # 缺失的字段按 0 补齐，保持序列稳定
    assert (
        'a_share_provider_operation_successes_total'
        '{operation="fallback_unavailable",provider="llm_chat"} 0' in text
    )


def test_provider_operations_absent_emits_no_series() -> None:
    text = _render({"providers": {"eastmoney": {"attempts": 1}}})
    assert "a_share_provider_operation_" not in text


def test_background_task_stop_reason_is_exported_as_labels() -> None:
    """停用/取消标记必须导出，否则告警无法区分「配置关闭」与「真的崩了」。"""
    text = _render(
        background_tasks={
            "twitter_feed": {
                "consecutive_errors": 0,
                "disabled_by_config": True,
                "cancelled_cleanly": False,
            },
            "quant_job_worker": {
                "consecutive_errors": 4,
                "disabled_by_config": False,
                "cancelled_cleanly": False,
            },
        }
    )
    assert 'a_share_background_task_disabled_by_config{task="twitter_feed"} 1' in text
    assert 'a_share_background_task_disabled_by_config{task="quant_job_worker"} 0' in text
    assert 'a_share_background_task_cancelled_cleanly{task="twitter_feed"} 0' in text


def test_background_task_stop_reason_defaults_to_zero_when_absent() -> None:
    """老快照没有这两个字段时不能凭空出现序列，也不能报错。"""
    text = _render(background_tasks={"daily_refresh": {"consecutive_errors": 1}})
    assert 'a_share_background_task_disabled_by_config{task="daily_refresh"} 0' in text
    assert 'a_share_background_task_cancelled_cleanly{task="daily_refresh"} 0' in text


def test_background_task_replica_active_distinguishes_standby() -> None:
    """standby 副本不跑周期任务，errors 恒 0；不给维度就分不清「健康」与「没轮到」。"""
    text = _render(
        background_tasks={
            "market_daily_bar_refresh": {"role": "leader", "consecutive_errors": 0},
            "database_backup": {"role": "standby", "consecutive_errors": 0},
            "quant_job_worker": {"role": "local", "consecutive_errors": 1},
        }
    )
    assert 'a_share_background_task_replica_active{task="market_daily_bar_refresh"} 1' in text
    assert 'a_share_background_task_replica_active{task="database_backup"} 0' in text
    # 不走选主的任务（每个副本都跑）同样算活跃
    assert 'a_share_background_task_replica_active{task="quant_job_worker"} 1' in text


def test_background_task_replica_active_defaults_to_active() -> None:
    """老快照没有 role 字段时，按 active 处理（不能凭空报成 standby）。"""
    text = _render(background_tasks={"legacy": {"consecutive_errors": 0}})
    assert 'a_share_background_task_replica_active{task="legacy"} 1' in text


def test_background_task_critical_flag_is_exported() -> None:
    """critical 决定「值不值得告警」，readiness_required 决定「要不要摘流量」。

    两者是独立运维动作：备份/预热挂了不该摘流量，但该告警。缺了这个维度，
    运维无法把关键任务和预热任务区分开。
    """
    text = _render(
        background_tasks={
            "quant_job_worker": {"critical": True, "readiness_required": True},
            "wal_checkpoint": {"critical": True, "readiness_required": False},
            "macro_analysis_prewarm": {"critical": False, "readiness_required": False},
        }
    )
    assert 'a_share_background_task_critical{task="quant_job_worker"} 1' in text
    assert 'a_share_background_task_critical{task="wal_checkpoint"} 1' in text
    assert 'a_share_background_task_critical{task="macro_analysis_prewarm"} 0' in text


def test_background_task_critical_defaults_to_zero() -> None:
    """没标 critical 的任务一律按非关键处理，不能凭空升级告警级别。"""
    text = _render(background_tasks={"legacy": {}})
    assert 'a_share_background_task_critical{task="legacy"} 0' in text


def test_national_team_metrics_are_rendered_with_trigger_and_source_labels() -> None:
    snapshot = {
        "national_team": {
            "attempts_total": 7,
            "failures_total": 2,
            "last_duration_ms": 1234.5,
            "last_success_timestamp": 1700000000.0,
            "coverage_ratio": 0.875,
            "partial": 1,
            "stale": 0,
            "covered_etf_count": 21,
            "total_etf_count": 24,
            "by_trigger": {
                "scheduled": {"attempts": 5, "failures": 1},
                "request": {"attempts": 2, "failures": 1},
            },
            "source_failures": {"sse": 3, "szse_history": 1},
        }
    }

    rendered = _render(snapshot)

    assert "a_share_national_team_refresh_attempts_total 7" in rendered
    assert "a_share_national_team_refresh_failures_total 2" in rendered
    assert "a_share_national_team_coverage_ratio 0.875" in rendered
    assert "a_share_national_team_partial 1" in rendered
    assert "a_share_national_team_covered_etfs 21" in rendered
    assert "a_share_national_team_total_etfs 24" in rendered
    assert 'a_share_national_team_refresh_by_trigger_attempts_total{trigger="scheduled"} 5' in rendered
    assert 'a_share_national_team_refresh_by_trigger_failures_total{trigger="request"} 1' in rendered
    assert 'a_share_national_team_source_failures_total{scope="sse"} 3' in rendered


def test_national_team_metrics_are_absent_when_snapshot_missing() -> None:
    # 未启用该模块时不要凭空输出一堆 0，否则告警规则很难写。
    assert "a_share_national_team_" not in _render({})
