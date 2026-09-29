"""概念计数的初始化校准与增量更新；调用方负责事务边界。"""

import json
import sqlite3
from collections import Counter
from collections.abc import Iterable


def concept_names(value: object) -> set[str]:
    if isinstance(value, str):
        try:
            value = json.loads(value)
        except (TypeError, ValueError):
            return set()
    if not isinstance(value, (list, tuple, set)):
        return set()
    return {str(item).strip() for item in value if isinstance(item, str) and item.strip()}


def concept_delta(before: object, after: object) -> Counter[str]:
    old, new = concept_names(before), concept_names(after)
    delta: Counter[str] = Counter({name: 1 for name in new - old})
    delta.subtract({name: 1 for name in old - new})
    return delta


def apply_concept_deltas(connection: sqlite3.Connection, deltas: Counter[str]) -> None:
    for name, change in sorted(deltas.items()):
        if not change:
            continue
        if change > 0:
            connection.execute(
                """INSERT INTO stock_concepts(name, stock_count) VALUES (?, ?)
                   ON CONFLICT(name) DO UPDATE SET
                     stock_count=stock_concepts.stock_count+excluded.stock_count,
                     updated_at=datetime('now','localtime')""",
                (name, change),
            )
        else:
            connection.execute(
                """UPDATE stock_concepts SET stock_count=stock_count+?,
                   updated_at=datetime('now','localtime') WHERE name=?""", (change, name),
            )
            connection.execute("DELETE FROM stock_concepts WHERE name=? AND stock_count<=0", (name,))


def rebuild_concept_counts(connection: sqlite3.Connection) -> None:
    counts: Counter[str] = Counter()
    rows: Iterable[sqlite3.Row] = connection.execute("SELECT concepts_json FROM stock_concept_mappings")
    for row in rows:
        counts.update(concept_names(row[0]))
    previous = {row[0]: row[1] for row in connection.execute("SELECT name, stock_count FROM stock_concepts")}
    for name, count in counts.items():
        if previous.get(name) != count:
            connection.execute(
                """INSERT INTO stock_concepts(name, stock_count) VALUES (?, ?)
                   ON CONFLICT(name) DO UPDATE SET stock_count=excluded.stock_count,
                   updated_at=datetime('now','localtime')""", (name, count),
            )
    connection.executemany("DELETE FROM stock_concepts WHERE name=?", [(name,) for name in previous.keys() - counts.keys()])
