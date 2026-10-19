"""Analyze agentic ``core_tools`` misses from a metrics snapshot.

The chat runtime records:

- ``skill_core_tool_missed:<tool>``: a non-core tool was added by ``load_skill``
- ``skill_load_after_initial:<skill>``: the model reloaded an already-active Skill
- ``skill_initial_tools_expanded`` / ``skill_tools_expanded``

Usage:

    python -m scripts.analyze_skill_core_misses metrics.json
    python -m scripts.analyze_skill_core_misses --url http://localhost:8000/api/health/metrics
    python -m scripts.analyze_skill_core_misses metrics.json --min-misses 5
"""

from __future__ import annotations

import argparse
import json
import urllib.request
from collections.abc import Mapping, Sequence
from pathlib import Path
from typing import Any

_MISS_PREFIX = "skill_core_tool_missed:"
_AFTER_INITIAL_PREFIX = "skill_load_after_initial:"
_SUMMARY_EVENTS = (
    "skill_load_success",
    "skill_initial_tools_expanded",
    "skill_tools_expanded",
    "skill_load_rejected",
    "skill_load_unknown",
)


def extract_events(payload: Mapping[str, Any]) -> dict[str, int]:
    """Accept either a raw metrics object or an ``/api/health/metrics`` response."""
    metrics = payload.get("metrics") if isinstance(payload.get("metrics"), Mapping) else payload
    agentic = metrics.get("agentic") if isinstance(metrics, Mapping) else None
    events = agentic.get("events") if isinstance(agentic, Mapping) else None
    if not isinstance(events, Mapping):
        return {}
    return {str(key): int(value) for key, value in events.items()}


def collect_prefixed(events: Mapping[str, int], prefix: str) -> dict[str, int]:
    return {
        key[len(prefix):]: value
        for key, value in events.items()
        if key.startswith(prefix) and key[len(prefix):]
    }


def tool_skill_map() -> dict[str, str]:
    """Map every declared tool to its Skill (best effort; empty if unavailable)."""
    try:
        from app.agentic_integration.skills.loader import load_builtin_skills
    except Exception:  # pragma: no cover - script runs without the app installed
        return {}
    return {
        tool: skill.name
        for skill in load_builtin_skills()
        for tool in skill.tool_names
    }


def core_tool_map() -> dict[str, frozenset[str]]:
    """Map skill name to its declared ``core_tools`` (empty = all tools)."""
    try:
        from app.agentic_integration.skills.loader import load_builtin_skills
    except Exception:  # pragma: no cover
        return {}
    return {
        skill.name: frozenset(skill.core_tool_names)
        for skill in load_builtin_skills()
    }


def build_report(
    events: Mapping[str, int],
    *,
    min_misses: int = 1,
) -> dict[str, Any]:
    misses = collect_prefixed(events, _MISS_PREFIX)
    after_initial = collect_prefixed(events, _AFTER_INITIAL_PREFIX)
    skills = tool_skill_map()
    cores = core_tool_map()
    rows: list[dict[str, Any]] = []
    for tool, count in sorted(misses.items(), key=lambda item: (-item[1], item[0])):
        skill = skills.get(tool)
        in_core = bool(skill and tool in cores.get(skill, frozenset()))
        rows.append({
            "tool": tool,
            "misses": count,
            "skill": skill,
            "in_core": in_core,
            "promote": count >= min_misses and not in_core,
        })
    return {
        "summary": {name: int(events.get(name, 0)) for name in _SUMMARY_EVENTS},
        "core_tool_misses": rows,
        "load_after_initial": dict(
            sorted(after_initial.items(), key=lambda item: (-item[1], item[0]))
        ),
    }


def render_text(report: Mapping[str, Any]) -> str:
    lines = ["Agentic Skill metrics"]
    for name, count in report["summary"].items():
        lines.append(f"  {name}: {count}")
    lines.append("")
    lines.append("Core tool misses (non-core tools added by load_skill)")
    rows: Sequence[Mapping[str, Any]] = report["core_tool_misses"]
    if not rows:
        lines.append("  (none)")
    for row in rows:
        marker = "  <= promote" if row["promote"] else ""
        lines.append(
            f"  {row['tool']:<40} misses={row['misses']:<5} "
            f"skill={row['skill'] or '?':<24} in_core={row['in_core']}{marker}"
        )
    lines.append("")
    lines.append("load_skill after initial activation (Skill rules/tools insufficient)")
    after_initial: Mapping[str, int] = report["load_after_initial"]
    if not after_initial:
        lines.append("  (none)")
    for skill, count in after_initial.items():
        lines.append(f"  {skill:<24} {count}")
    return "\n".join(lines)


def _load_payload(args: argparse.Namespace) -> Mapping[str, Any]:
    if args.url:
        with urllib.request.urlopen(args.url, timeout=args.timeout) as response:
            return json.loads(response.read().decode("utf-8"))
    return json.loads(Path(args.path).read_text(encoding="utf-8"))


def main(argv: Sequence[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("path", nargs="?", help="metrics JSON file")
    parser.add_argument("--url", help="fetch metrics JSON from a URL")
    parser.add_argument("--timeout", type=float, default=10.0)
    parser.add_argument(
        "--min-misses",
        type=int,
        default=1,
        help="mark tools with at least this many misses as promotion candidates",
    )
    parser.add_argument("--json", action="store_true", help="emit JSON instead of text")
    args = parser.parse_args(argv)
    if not args.path and not args.url:
        parser.error("需要提供 metrics JSON 路径或 --url")

    report = build_report(extract_events(_load_payload(args)), min_misses=args.min_misses)
    if args.json:
        print(json.dumps(report, ensure_ascii=False, indent=2))
    else:
        print(render_text(report))
    return 0


if __name__ == "__main__":  # pragma: no cover
    raise SystemExit(main())
