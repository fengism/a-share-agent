from dataclasses import dataclass
from datetime import datetime


@dataclass(frozen=True)
class BaseDataProvider:
    """Purpose: 数据提供者的基类，包含名称、来源标签及通用时间戳解析能力。"""

    name: str
    source_label: str

    def log_prefix(self, capability: str) -> str:
        """Build a log prefix string combining source label and capability.

        Param:
            capability: capability name to append to the source label
        Return:
            combined string used as a logging prefix
        """
        return f"{self.source_label}{capability}"

    @staticmethod
    def _parse_timestamp(value) -> datetime | None:
        """Parse a timestamp value (unix seconds or milliseconds) into datetime.

        Param:
            value: timestamp as int, float, or string (seconds or milliseconds)
        Return:
            parsed datetime, or None if value is empty or unparseable
        """
        if value in (None, "", 0, "0"):
            return None
        try:
            ts = int(float(value))
        except (TypeError, ValueError):
            return None
        if ts > 10**12:
            ts = ts / 1000
        try:
            return datetime.fromtimestamp(ts)
        except (OverflowError, OSError, ValueError):
            return None
