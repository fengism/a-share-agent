"""Evidence identity/state caching must not change the public contract."""

import json
from dataclasses import asdict

from app.agentic import contracts
from app.agentic.contracts import AgentEvidence, agent_evidence_id


def _evidence(content: str | None = None, *, arguments: str = '{"code":"600519"}') -> AgentEvidence:
    return AgentEvidence(
        tool_call_id="call_1",
        tool_name="get_stock_info",
        arguments=arguments,
        content=content if content is not None else json.dumps({"ok": True, "data": {"code": "600519"}}),
    )


def test_agent_evidence_id_is_computed_once_per_instance(monkeypatch):
    evidence = _evidence()
    calls = 0
    original = contracts._agent_evidence_id

    def counting(item: AgentEvidence) -> str:
        nonlocal calls
        calls += 1
        return original(item)

    monkeypatch.setattr(contracts, "_agent_evidence_id", counting)

    first = agent_evidence_id(evidence)
    second = agent_evidence_id(evidence)

    assert first == second
    assert first.startswith("ev_")
    assert calls == 1


def test_evidence_state_is_cached_per_instance():
    evidence = _evidence()

    assert evidence.evidence_state is evidence.evidence_state
    assert evidence.evidence_state.usable_acquisition is True


def test_cached_properties_are_not_dataclass_fields():
    evidence = _evidence()

    # as_tool_payload() uses asdict(); cached properties must not leak into it.
    assert set(asdict(evidence)) == {
        "tool_call_id",
        "tool_name",
        "arguments",
        "content",
        "is_error",
    }


def test_evidence_id_ignores_volatile_timestamps():
    first = _evidence(json.dumps({"ok": True, "data": {"text": "x", "fetched_at": "2025-01-01"}}))
    second = _evidence(json.dumps({"ok": True, "data": {"text": "x", "fetched_at": "2025-01-02"}}))

    assert agent_evidence_id(first) == agent_evidence_id(second)


def test_evidence_id_still_normalizes_argument_key_order():
    first = _evidence(arguments='{"code":"600519","market":"cn"}')
    second = _evidence(arguments='{"market":"cn","code":"600519"}')

    assert agent_evidence_id(first) == agent_evidence_id(second)
