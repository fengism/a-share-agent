"""Chat 模块对其他业务模块开放的稳定入口。"""

from app.modules.chat.availability import build_capability_availability

__all__ = [
    "build_capability_availability",
]
