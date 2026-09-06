import re

from app.modules.industry_chain.charts import build_industry_charts
from app.modules.industry_chain.models import IndustryChainNode, IndustryChainResult
from app.modules.industry_chain.report_renderer import render_industry_markdown

_A_SHARE_CODE_PATTERN = re.compile(
    r"^(?:(?:SH|SZ|BJ)[.:]?)?"
    r"((?:00|30|60|68|43|83|87)\d{4}|920\d{3})"
    r"(?:[.:]?(?:SH|SZ|BJ))?$",
    re.IGNORECASE,
)


def _string_value(value) -> str:
    if value is None or isinstance(value, (dict, list)):
        return ""
    return str(value).strip()


def _string_list(value) -> list[str]:
    if not isinstance(value, list):
        return []
    return [text for item in value if (text := _string_value(item))]


def _stock_code(value) -> str:
    code = _string_value(value)
    match = _A_SHARE_CODE_PATTERN.fullmatch(code)
    return match.group(1) if match else code


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
        node["code"] = _stock_code(node.get("code"))
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


def _find_stock_code_from_text(text: str, reverse_map: dict[str, str]) -> str:
    if not text:
        return ""
    clean_text = text.strip()
    if clean_text in reverse_map:
        return reverse_map[clean_text]
    for name, code in reverse_map.items():
        if len(name) >= 3 and (name in clean_text or clean_text in name):
            return code
    return ""


def enrich_result_stock_codes(
    result: IndustryChainResult,
    name_map: dict[str, str],
) -> IndustryChainResult:
    """基于全市场 5000+ 股票名称代码映射表，自动补齐并修正产业链各环节公司代码与名称。"""
    if not name_map:
        return result
    reverse_map = {name.strip(): code.strip() for code, name in name_map.items() if name}

    def enrich_node(node) -> IndustryChainNode:
        code = (node.code or "").strip()
        name = (node.name or "").strip()
        company = (node.company or "").strip()

        if code and code in name_map:
            if not name or name == code:
                node.name = name_map[code]

        if not code:
            candidates = [name, company, *node.companies]
            for cand in candidates:
                found_code = _find_stock_code_from_text(cand, reverse_map)
                if found_code:
                    node.code = found_code
                    if not node.name:
                        node.name = name_map.get(found_code, cand)
                    break
        return node

    result.key_stocks = [enrich_node(node) for node in result.key_stocks]
    result.upstream = [enrich_node(node) for node in result.upstream]
    result.midstream = [enrich_node(node) for node in result.midstream]
    result.downstream = [enrich_node(node) for node in result.downstream]
    for group in result.competition:
        group.companies = [enrich_node(node) for node in group.companies]

    return result
