"""CSV 导出公式注入防护（CSV injection）测试。

导出文件里的公司简称/概念/行业/主营业务等字段来自同步任务与管理员编辑，
属于半可信输入。若不做转义，``=cmd|'/c calc'!A1`` 之类的内容会在打开
Excel/WPS 时被当公式执行。
"""

from __future__ import annotations

import ast
import csv
import io

import pytest

from app.api.routes import industry_classification as industry_routes
from app.api.routes import stock_concept as concept_routes
from app.core.csv_export import csv_safe_cell, csv_safe_row
from app.modules.stock_profile import service as profile_service

PAYLOAD = "=cmd|'/c calc'!A1"


@pytest.mark.parametrize(
    "raw",
    [
        PAYLOAD,
        "+1+1",
        "-2+3",
        "@SUM(A1:A2)",
        '=HYPERLINK("http://evil")',
        "\t=1+1",
        "\r=1+1",
        "  =1+1",
        "\ufeff=1+1",
    ],
)
def test_formula_like_cells_are_prefixed(raw: str) -> None:
    escaped = csv_safe_cell(raw)
    assert escaped == "'" + raw


@pytest.mark.parametrize(
    "raw",
    ["600519", "贵州茅台", "0.5", "-1.5", "+3.2e5", "-0.00", "", "  ", "普通文本-带横线"],
)
def test_plain_values_are_untouched(raw: str) -> None:
    assert csv_safe_cell(raw) == raw


def test_none_becomes_empty_and_numbers_become_text() -> None:
    assert csv_safe_cell(None) == ""
    assert csv_safe_cell(3) == "3"
    assert csv_safe_cell(-4.25) == "-4.25"


def test_row_helper_maps_every_column() -> None:
    assert csv_safe_row(["600519", PAYLOAD, None, 42]) == ["600519", "'" + PAYLOAD, "", "42"]


def _csv_body(rows: list[list[object]]) -> list[list[str]]:
    buffer = io.StringIO()
    writer = csv.writer(buffer)
    for row in rows:
        writer.writerow(csv_safe_row(row))
    return list(csv.reader(io.StringIO(buffer.getvalue())))


async def _drain(response: object) -> str:
    chunks = [chunk async for chunk in response.body_iterator]  # type: ignore[attr-defined]
    return b"".join(chunks).decode("utf-8")


@pytest.mark.asyncio
async def test_concept_export_escapes_formula_cells(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(
        concept_routes,
        "list_records",
        lambda **_kwargs: (
            [
                {
                    "stock_code": "600519",
                    "stock_name": PAYLOAD,
                    "market_group": "A",
                    "concepts": [PAYLOAD, "白酒"],
                    "source": "eastmoney",
                    "updated_at": "2026-01-01 10:00:00",
                }
            ],
            1,
        ),
    )

    body = await _drain(concept_routes.export_concepts())
    rows = list(csv.reader(io.StringIO(body.lstrip("\ufeff"))))
    assert rows[0][0] == "股票代码"
    exported = rows[1]
    assert exported[1] == "'" + PAYLOAD
    # 概念列按「；」拼成一格；恶意内容排在最前面时整格以 = 开头，必须转义
    assert exported[3] == "'" + PAYLOAD + "；白酒"


@pytest.mark.asyncio
async def test_industry_export_escapes_formula_cells(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(
        industry_routes,
        "list_records",
        lambda **_kwargs: (
            [
                {
                    "stock_code": "600519",
                    "stock_name": "贵州茅台",
                    "market_group": "A",
                    "sw_level1_name": PAYLOAD,
                    "sw_level2_name": "-2+3",
                    "sw_level3_name": "白酒",
                    "sw_industry_code": "340500",
                    "source": "sw",
                    "updated_at": "2026-01-01 10:00:00",
                }
            ],
            1,
        ),
    )

    body = await _drain(industry_routes.export_industries())
    rows = list(csv.reader(io.StringIO(body.lstrip("\ufeff"))))
    exported = rows[1]
    assert exported[1] == "贵州茅台"
    assert exported[3] == "'" + PAYLOAD
    assert exported[4] == "'-2+3"


@pytest.mark.asyncio
async def test_profile_export_escapes_formula_cells(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(
        profile_service,
        "list_records",
        lambda **_kwargs: (
            [
                {
                    "stock_code": "600519",
                    "stock_name": PAYLOAD,
                    "exchange": "SSE",
                    "board": "主板",
                    "listing_date": "2001-08-27",
                    "industry": "白酒",
                    "sw_level1_name": "食品饮料",
                    "sw_level2_name": "白酒Ⅱ",
                    "sw_level3_name": "白酒Ⅲ",
                    "main_business": "@SUM(1+1)",
                    "business_scope": "白酒生产与销售",
                    "products": "茅台酒",
                    "province": "贵州",
                }
            ],
            1,
        ),
    )

    payload_bytes, disposition = profile_service.export_profiles_csv()
    assert disposition.startswith("attachment;")
    rows = list(csv.reader(io.StringIO(payload_bytes.decode("utf-8").lstrip("\ufeff"))))
    exported = rows[1]
    assert exported[1] == "'" + PAYLOAD
    assert exported[9] == "'@SUM(1+1)"
    assert exported[0] == "600519"


def test_every_csv_export_route_uses_the_safe_helper() -> None:
    """所有导出 CSV 的数据行都必须经过 csv_safe_row，避免新增导出时漏防护。"""
    sources = {
        "app/api/routes/industry_classification.py": industry_routes.__file__,
        "app/api/routes/stock_concept.py": concept_routes.__file__,
        "app/modules/stock_profile/service.py": profile_service.__file__,
    }
    for name, path in sources.items():
        assert path is not None
        tree = ast.parse(open(path, encoding="utf-8").read())
        data_rows = []
        for node in ast.walk(tree):
            if not isinstance(node, ast.Call) or not node.args:
                continue
            func = node.func
            if not isinstance(func, ast.Attribute) or func.attr != "writerow":
                continue
            argument = node.args[0]
            if isinstance(argument, ast.Call):
                callee = argument.func
                if isinstance(callee, ast.Name) and callee.id == "csv_safe_row":
                    continue
            expression = ast.unparse(argument)
            # 表头是常量字面量/常量表的推导式；含 .get( 的才是来自记录的导出数据
            if ".get(" in expression:
                data_rows.append(f"{name}:{node.lineno} {expression[:60]}")
        assert data_rows == [], data_rows
