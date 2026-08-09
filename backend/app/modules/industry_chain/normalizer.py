from app.modules.industry_chain.models import IndustryChainResult


def unescape_json_string(value: str) -> str:
    """简单反转义 JSON 字符串中的换行、引号和反斜杠。"""
    result = []
    index = 0
    while index < len(value):
        if value[index] == "\\" and index + 1 < len(value):
            next_character = value[index + 1]
            replacements = {"n": "\n", "r": "\r", "t": "\t", '"': '"', "\\": "\\"}
            replacement = replacements.get(next_character)
            if replacement is None:
                result.extend((value[index], next_character))
            else:
                result.append(replacement)
            index += 2
        else:
            result.append(value[index])
            index += 1
    return "".join(result)


def extract_llm_report(text: str) -> str | None:
    """结构化校验失败时，从原始响应中恢复 llm_report 字段。"""
    for prefix in ('"llm_report"', "'llm_report'"):
        prefix_index = text.find(prefix)
        if prefix_index == -1:
            continue
        after_prefix = text[prefix_index + len(prefix):]
        colon_index = after_prefix.find(":")
        if colon_index == -1:
            continue
        content = after_prefix[colon_index + 1:].lstrip()
        if not content or content[0] not in ('"', "'"):
            continue
        delimiter = content[0]
        index = 1
        while index < len(content):
            if content[index] == "\\":
                index += 2
                continue
            if content[index] == delimiter:
                return content[1:index]
            index += 1
    return None


def enhance_chart_options(charts: list) -> list:
    """补全产业链图表在暗色主题下运行所需的 ECharts 配置。"""
    enhanced = []
    for chart in charts:
        if not isinstance(chart, dict):
            continue
        option = chart.get("option", {})
        if not isinstance(option, dict):
            chart["option"] = {}
            enhanced.append(chart)
            continue

        chart_type = chart.get("type", "")
        series = option.get("series", [])
        option.setdefault("backgroundColor", "transparent")
        if "tooltip" not in option:
            if chart_type == "tree":
                option["tooltip"] = {"trigger": "item", "triggerOn": "mousemove"}
            else:
                option["tooltip"] = {
                    "trigger": "axis",
                    "backgroundColor": "rgba(15,23,42,0.9)",
                    "borderColor": "#334155",
                    "textStyle": {"color": "#e5e7eb", "fontSize": 12},
                }

        if chart_type in ("bar", "line") and "grid" not in option:
            option["grid"] = {"containLabel": True, "left": 40, "right": 20, "bottom": 40, "top": 20}
        elif chart_type in ("bar", "line") and isinstance(option.get("grid"), dict):
            option["grid"]["containLabel"] = option["grid"].get("containLabel", True)

        if chart_type in ("bar", "line"):
            for axis_key in ("xAxis", "yAxis"):
                axes = option.get(axis_key)
                if isinstance(axes, dict):
                    axes = [axes]
                if not isinstance(axes, list):
                    continue
                for axis in axes:
                    axis_label = axis.get("axisLabel") if isinstance(axis, dict) else None
                    if isinstance(axis_label, dict):
                        axis_label.setdefault("color", "#9ca3af")

        if chart_type == "tree":
            for item in series if isinstance(series, list) else []:
                if not isinstance(item, dict) or item.get("type") != "tree":
                    continue
                item.setdefault("roam", True)
                item.setdefault("top", 20)
                item.setdefault("left", 80)
                item.setdefault("bottom", 20)
                item.setdefault("right", 80)
                item.setdefault("expandAndCollapse", True)
                item.setdefault("initialTreeDepth", 5)
                item.setdefault("lineStyle", {"color": "#4b5563", "width": 1.5})
                item.setdefault("label", {"position": "left", "fontSize": 12, "color": "#e5e7eb"})
                item.setdefault("leaves", {"label": {"position": "right", "fontSize": 12, "color": "#e5e7eb"}})

        chart["option"] = option
        enhanced.append(chart)
    return enhanced


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
        for field in ("name", "company", "code", "role", "description", "market_share", "metric", "source"):
            node[field] = _string_value(node.get(field))
        node["companies"] = _string_list(node.get("companies"))
        nodes.append(node)
    return nodes


def _competition_list(value) -> list[dict]:
    groups = _record_list(value, ("market", "summary"))
    for group in groups:
        group["companies"] = _node_list(group.get("companies"))
    return groups


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
    return IndustryChainResult(
        schema_version=2,
        name=name,
        aliases=_string_list(parsed.get("aliases")),
        summary=_string_value(parsed.get("summary")),
        positioning=_string_value(parsed.get("positioning")),
        market_metrics=_record_list(
            parsed.get("market_metrics"),
            ("label", "value", "period", "growth", "source", "source_url"),
        ),
        competition=_competition_list(parsed.get("competition")),
        technology_routes=_record_list(parsed.get("technology_routes"), ("title", "detail", "evidence", "source")),
        upstream=_section_nodes(parsed, "upstream"),
        midstream=_section_nodes(parsed, "midstream"),
        downstream=_section_nodes(parsed, "downstream"),
        drivers=_string_list(parsed.get("drivers")),
        trends=_record_list(parsed.get("trends"), ("title", "detail", "evidence", "source")),
        risks=_string_list(parsed.get("risks")),
        capital_moves=_record_list(parsed.get("capital_moves"), ("title", "detail", "evidence", "source")),
        key_events=_record_list(parsed.get("key_events"), ("date", "title", "impact", "source", "source_url")),
        key_stocks=_node_list(parsed.get("key_stocks")),
        sources=_record_list(parsed.get("sources"), ("title", "publisher", "date", "url")),
        llm_review=_string_value(parsed.get("llm_report") or parsed.get("llm_review")),
        charts=enhance_chart_options(parsed.get("charts", [])),
    )
