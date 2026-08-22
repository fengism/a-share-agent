from dataclasses import dataclass
from typing import Literal


@dataclass
class ContentBlock:
    """飞书、Notion 等内容集成共用的文档片段。"""

    type: Literal["heading", "paragraph", "bullet", "divider"]
    level: int = 0
    text: str = ""
