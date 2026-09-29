"""Industry report recovery and whole-report cache policy."""

from __future__ import annotations

import json
from collections.abc import Callable

from app.domain.industry_chain import IndustryChainResearchScope
from app.infrastructure.llm.prompting.parsing import extract_json_object
from app.modules.industry_chain.models import IndustryChainResult
from app.modules.industry_chain.prompts import INDUSTRY_CHAIN_PROMPT_SPEC

RESULT_CACHE_TTL_SECONDS = 24 * 60 * 60
DEGRADED_RESULT_CACHE_TTL_SECONDS = 10 * 60


class IndustryChainReportUnavailableError(RuntimeError):
    """No usable structured report could be produced or recovered."""


def has_usable_report_structure(result: IndustryChainResult) -> bool:
    return bool(result.summary.strip() and (result.upstream or result.midstream or result.downstream))


def recover_prompt_result(
    name: str,
    raw_response: str,
    result_factory: Callable[[str, dict], IndustryChainResult],
) -> IndustryChainResult | None:
    """Best-effort recovery for schema-invalid JSON without inventing content."""
    try:
        payload = json.loads(extract_json_object(raw_response))
        if not isinstance(payload, dict):
            return None
        result = result_factory(name, payload)
    except (TypeError, ValueError, json.JSONDecodeError):
        return None
    return result if has_usable_report_structure(result) else None


def industry_chain_cache_key(user_id: int, name: str, scope: IndustryChainResearchScope) -> str:
    scope_payload = scope.model_dump(mode="json", exclude={"refresh_dimensions"})
    scope_cache_text = json.dumps(scope_payload, ensure_ascii=False, sort_keys=True, separators=(",", ":"))
    return INDUSTRY_CHAIN_PROMPT_SPEC.cache_key("user", user_id, name, scope_cache_text)


def result_cache_ttl(result: IndustryChainResult) -> int:
    return RESULT_CACHE_TTL_SECONDS if result.quality_status == "complete" else DEGRADED_RESULT_CACHE_TTL_SECONDS
