from dataclasses import dataclass
from typing import Literal


@dataclass
class ContentBlock:
    """飞书、Notion 等内容集成共用的文档片段。

    image 块通过 image_key 引用已上传到飞书的图片；不支持图片的
    渠道（如 Notion、飞书文档）应静默跳过而不是报错。
    """

    type: Literal["heading", "paragraph", "bullet", "divider", "image"]
    level: int = 0
    text: str = ""
    image_key: str = ""
