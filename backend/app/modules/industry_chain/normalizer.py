from app.modules.industry_chain.charts import build_industry_charts
from app.modules.industry_chain.models import IndustryChainResult
from app.modules.industry_chain.report_renderer import render_industry_markdown


def _string_value(value) -> str:
    if value is None or isinstance(value, (dict, list)):
        return ""
    return str(value).strip()


def _string_list(value) -> list[str]:
    if not isinstance(value, list):
        return []
    return [text for item in value if (text := _string_value(item))]


def _record_list(value, string_fields: tuple[str, ...]) -> list[dict]:
    if not isinstance(value, list):
        return []
    records = []
    for item in value:
        if not isinstance(item, dict):
            continue
        record = dict(item)
        for field in string_fields:
            record[field] = _string_value(record.get(field))
        record["evidence_ids"] = _string_list(record.get("evidence_ids"))
        records.append(record)
    return records


def _node_list(value) -> list[dict]:
    if not isinstance(value, list):
        return []
    nodes = []
    for item in value:
        if isinstance(item, str):
            nodes.append({"name": item})
            continue
        if not isinstance(item, dict):
            continue
        node = dict(item)
        for field in (
            "name", "company", "code", "role", "description", "market_share", "metric", "source", "source_url",
        ):
            node[field] = _string_value(node.get(field))
        node["companies"] = _string_list(node.get("companies"))
        node["evidence_ids"] = _string_list(node.get("evidence_ids"))
        nodes.append(node)
    return nodes


def _competition_list(value) -> list[dict]:
    groups = _record_list(value, ("market", "summary"))
    for group in groups:
        group["companies"] = _node_list(group.get("companies"))
    return groups


def _insight_list(value) -> list[dict]:
    if not isinstance(value, list):
        return []
    normalized = []
    for item in value:
        if isinstance(item, str):
            if item.strip():
                normalized.append({"title": item.strip()})
            continue
        if isinstance(item, dict):
            normalized.extend(_record_list([item], ("title", "detail", "evidence", "source", "source_url")))
    return normalized


def _conflict_list(value) -> list[dict]:
    records = _record_list(value, ("topic", "reason"))
    for record in records:
        record["values"] = _string_list(record.get("values"))
    return records


def _section_nodes(parsed: dict, level: str) -> list[dict]:
    direct = _node_list(parsed.get(level))
    if direct:
        return direct
    sections = parsed.get("sections")
    if not isinstance(sections, list):
        return []
    nodes = []
    for section in sections:
        if not isinstance(section, dict) or section.get("level") != level:
            continue
        section_items = _node_list(section.get("items"))
        nodes.extend(section_items or _node_list([section]))
    return nodes


def result_from_payload(name: str, parsed: dict) -> IndustryChainResult:
    """把 LLM JSON 归一化为向后兼容的结构化产业链结果。"""
    driver_insights = _insight_list(parsed.get("driver_insights") or parsed.get("drivers"))
    risk_insights = _insight_list(parsed.get("risk_insights") or parsed.get("risks"))
    result = IndustryChainResult(
        schema_version=7,
        name=name,
        aliases=_string_list(parsed.get("aliases")),
        summary=_string_value(parsed.get("summary")),
        positioning=_string_value(parsed.get("positioning")),
        summary_evidence_ids=_string_list(parsed.get("summary_evidence_ids")),
        positioning_evidence_ids=_string_list(parsed.get("positioning_evidence_ids")),
        market_metrics=_record_list(
            parsed.get("market_metrics"),
            ("label", "value", "period", "growth", "source", "source_url"),
        ),
        competition=_competition_list(parsed.get("competition")),
        technology_routes=_insight_list(parsed.get("technology_routes")),
        upstream=_section_nodes(parsed, "upstream"),
        midstream=_section_nodes(parsed, "midstream"),
        downstream=_section_nodes(parsed, "downstream"),
        drivers=[item.get("title", "") for item in driver_insights if item.get("title")],
        driver_insights=driver_insights,
        trends=_insight_list(parsed.get("trends")),
        risks=[item.get("title", "") for item in risk_insights if item.get("title")],
        risk_insights=risk_insights,
        capital_moves=_insight_list(parsed.get("capital_moves")),
        key_events=_record_list(parsed.get("key_events"), ("date", "title", "impact", "source", "source_url")),
        key_stocks=_node_list(parsed.get("key_stocks")),
        sources=_record_list(parsed.get("sources"), ("title", "publisher", "date", "url")),
        llm_review="",
        charts=[],
        coverage=parsed.get("coverage") if isinstance(parsed.get("coverage"), dict) else {},
        missing_evidence=_string_list(parsed.get("missing_evidence")),
        conflicts=_conflict_list(parsed.get("conflicts")),
    )
    result.charts = build_industry_charts(result)
    result.llm_review = render_industry_markdown(result)
    return result
