"""LIKE 模式转义：用户关键词里的 % 与 _ 必须按字面量匹配。"""

from __future__ import annotations

import sqlite3

import pytest

from app.core.sql import contains_pattern, escape_like, prefix_pattern


@pytest.fixture()
def db() -> sqlite3.Connection:
    connection = sqlite3.connect(":memory:")
    connection.execute("CREATE TABLE t (name TEXT)")
    connection.executemany(
        "INSERT INTO t VALUES (?)",
        [("贵州茅台",), ("平安银行",), ("宁德时代",), ("100%纯棉",), ("a_b",)],
    )
    return connection


def _search(connection: sqlite3.Connection, pattern: str) -> list[str]:
    rows = connection.execute(
        "SELECT name FROM t WHERE name LIKE ? ESCAPE '\\' ORDER BY name", (pattern,)
    ).fetchall()
    return [row[0] for row in rows]


def test_escape_like_handles_all_metacharacters() -> None:
    assert escape_like("100%") == "100\\%"
    assert escape_like("a_b") == "a\\_b"
    # 转义符本身要先被转义，否则会破坏后续的 \% / \_
    assert escape_like("a\\b") == "a\\\\b"
    assert escape_like("百分号%下划线_反斜杠\\") == "百分号\\%下划线\\_反斜杠\\\\"


def test_escape_like_leaves_plain_text_untouched() -> None:
    assert escape_like("贵州茅台") == "贵州茅台"
    assert escape_like("") == ""


def test_percent_input_does_not_match_everything(db: sqlite3.Connection) -> None:
    """裸 '%' 曾是通配符，会把整表都搜出来。"""
    assert _search(db, contains_pattern("%")) == ["100%纯棉"]
    assert _search(db, contains_pattern("%")) != ["100%纯棉", "a_b", "平安银行", "宁德时代", "贵州茅台"]


def test_underscore_input_does_not_match_single_char(db: sqlite3.Connection) -> None:
    assert _search(db, contains_pattern("_")) == ["a_b"]


def test_contains_pattern_still_matches_substring(db: sqlite3.Connection) -> None:
    assert _search(db, contains_pattern("茅台")) == ["贵州茅台"]
    assert _search(db, contains_pattern("100%")) == ["100%纯棉"]


def test_prefix_pattern_is_anchored(db: sqlite3.Connection) -> None:
    assert _search(db, prefix_pattern("贵州")) == ["贵州茅台"]
    assert _search(db, prefix_pattern("茅台")) == []
