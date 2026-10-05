"""申万行业记录对缺失 effective_date 的容错测试。

背景：历史/种子数据把缺失的 effective_date 存成空串，而 IndustryRecordInput
把 effective_date 声明为 date | None，空串解析失败会让 GET /industry-classification
/stocks 整个列表返回 400。空串必须被当作缺失处理。
"""

from __future__ import annotations

from datetime import date

from app.modules.industry_classification.models import IndustryRecord, IndustryRecordInput


def _payload(**overrides: object) -> dict[str, object]:
    data: dict[str, object] = {
        "market_group": "A",
        "exchange_suffix": "SZ",
        "stock_code": "000001",
        "stock_name": "平安银行",
        "sw_level1_name": "银行",
        "sw_level2_name": "",
        "sw_level3_name": "",
        "sw_industry_code": "",
        "source_version": "",
        "effective_date": "",
    }
    data.update(overrides)
    return data


def test_empty_effective_date_parses_as_none() -> None:
    record = IndustryRecordInput.model_validate(_payload())
    assert record.effective_date is None


def test_valid_effective_date_is_preserved() -> None:
    record = IndustryRecordInput.model_validate(_payload(effective_date="2026-09-30"))
    assert record.effective_date == date(2026, 9, 30)


def test_industry_record_with_empty_effective_date_does_not_raise() -> None:
    record = IndustryRecord.model_validate(
        {
            **_payload(),
            "id": 1,
            "revision": "x" * 64,
            "source": "seed",
            "is_manual_override": False,
            "created_at": "2026-09-30 10:00:00",
            "updated_at": "2026-09-30 10:00:00",
        }
    )
    assert record.effective_date is None
