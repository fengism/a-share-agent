"""手工写入的唯一约束冲突必须被翻译成领域错误。

背景：API 层原本直接 ``except sqlite3.IntegrityError``，把存储实现细节泄漏到了
HTTP 层。现在数据访问层统一翻译为 ``*RecordConflictError``，本测试锁定该契约，
防止后续重构又把 sqlite3 异常冒泡上去。
"""

from __future__ import annotations

from collections.abc import Callable

import pytest

from app.modules.industry_classification import repository as industry_repo
from app.modules.industry_classification.models import IndustryRecordInput
from app.modules.stock_concept import repository as concept_repo
from app.modules.stock_concept.models import StockConceptRecordInput


def _purge(
    get_record: Callable[[str], dict[str, object] | None],
    delete_record: Callable[[int], bool],
    stock_code: str,
) -> None:
    """删除可能由历史测试运行遗留的记录，保证用例可重复执行。"""
    existing = get_record(stock_code)
    if existing is not None:
        delete_record(int(existing["id"]))


def test_duplicate_industry_stock_code_raises_domain_conflict() -> None:
    stock_code = "990001"
    _purge(industry_repo.get_record, industry_repo.delete_record, stock_code)
    payload = IndustryRecordInput.model_validate(
        {
            "market_group": "A",
            "exchange_suffix": "SZ",
            "stock_code": stock_code,
            "stock_name": "冲突测试",
            "sw_level1_name": "银行",
            "sw_level2_name": "",
            "sw_level3_name": "",
            "sw_industry_code": "",
            "source_version": "",
            "effective_date": "",
        }
    )
    try:
        industry_repo.create_manual(payload)

        with pytest.raises(industry_repo.IndustryRecordConflictError) as excinfo:
            industry_repo.create_manual(payload)

        assert str(excinfo.value) == "股票代码已存在"
        # 异常链保留原始存储层原因，便于排障
        assert excinfo.value.__cause__ is not None
    finally:
        _purge(industry_repo.get_record, industry_repo.delete_record, stock_code)


def test_duplicate_stock_concept_code_raises_domain_conflict() -> None:
    stock_code = "990002"
    _purge(concept_repo.get_record, concept_repo.delete_record, stock_code)
    payload = StockConceptRecordInput.model_validate(
        {
            "market_group": "A",
            "exchange_suffix": "SZ",
            "stock_code": stock_code,
            "stock_name": "冲突测试",
            "concepts": ["测试概念"],
            "source_version": "",
        }
    )
    try:
        concept_repo.create_manual(payload)

        with pytest.raises(concept_repo.StockConceptRecordConflictError) as excinfo:
            concept_repo.create_manual(payload)

        # StockConceptRecordInput 会把代码规范化为带交易所后缀的形式
        assert str(excinfo.value) == "股票代码 990002.SZ 已存在"
    finally:
        _purge(concept_repo.get_record, concept_repo.delete_record, stock_code)
