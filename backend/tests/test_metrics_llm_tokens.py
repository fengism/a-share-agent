"""Per-call LLM token maxima: the data needed to tune prompt/completion budgets."""

from __future__ import annotations

from app.core.metrics import MetricsRegistry


def _record(registry: MetricsRegistry, prompt_tokens: int | None, completion_tokens: int | None) -> None:
    registry.record_llm_prompt(
        "agentic.stream@v1",
        "fake-model",
        success=True,
        duration_ms=10.0,
        prompt_tokens=prompt_tokens,
        completion_tokens=completion_tokens,
    )


def test_token_totals_and_maxima_are_both_tracked():
    registry = MetricsRegistry()

    _record(registry, 1_000, 200)
    _record(registry, 8_000, 4_096)
    _record(registry, 3_000, 100)

    entry = registry.snapshot()["llm"]["prompts"]["agentic.stream@v1"]["fake-model"]
    assert entry["prompt_tokens"] == 12_000
    assert entry["prompt_tokens_max"] == 8_000
    assert entry["completion_tokens"] == 4_396
    assert entry["completion_tokens_max"] == 4_096


def test_missing_usage_does_not_reset_the_maximum():
    registry = MetricsRegistry()

    _record(registry, 5_000, 1_000)
    _record(registry, None, None)

    entry = registry.snapshot()["llm"]["prompts"]["agentic.stream@v1"]["fake-model"]
    assert entry["prompt_tokens_max"] == 5_000
    assert entry["completion_tokens_max"] == 1_000
    assert entry["attempts"] == 2
