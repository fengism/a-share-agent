"""基于完整存量记录的修订标识；检查必须在写事务内执行。"""

import hashlib
import json
from collections.abc import Mapping
from typing import Any


class MasterDataConflictError(RuntimeError):
    pass


def record_revision(record: Mapping[str, Any]) -> str:
    values = {key: value for key, value in dict(record).items() if key != "revision"}
    return hashlib.sha256(json.dumps(values, sort_keys=True, ensure_ascii=False, default=str).encode()).hexdigest()


def check_revision(current: Mapping[str, Any] | None, expected: str) -> None:
    if current is None or record_revision(current) != expected:
        raise MasterDataConflictError("记录已被其他操作更新或删除，请重新加载并核对修改后再保存")
