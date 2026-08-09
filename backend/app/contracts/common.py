"""跨业务模块复用的通用 HTTP 响应契约。"""

from pydantic import BaseModel


class DeleteResponse(BaseModel):
    deleted: bool = True
