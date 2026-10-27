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
