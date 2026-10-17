"""在 JSON 解析前限制导入请求；同时覆盖 Content-Length 与分块上传。"""

from collections import deque
from typing import Any

from starlette.responses import JSONResponse

from app.modules.import_limits import IMPORT_PATHS, MAX_IMPORT_REQUEST_BYTES


class ImportBodyLimitMiddleware:
    def __init__(self, app, max_bytes: int = MAX_IMPORT_REQUEST_BYTES):
        self.app = app
        self.max_bytes = max_bytes

    async def __call__(self, scope, receive, send):
        if scope.get("type") != "http" or scope.get("path", "").rstrip("/") not in IMPORT_PATHS:
            return await self.app(scope, receive, send)

        async def reject():
            await JSONResponse(
                {"code": "master_data.upload_too_large", "message": "导入文件不能超过 50 MiB（请求体上限 70 MiB）"},
                status_code=413,
            )(scope, receive, send)

        for key, value in scope.get("headers", []):
            if key.lower() == b"content-length":
                try:
                    if int(value) > self.max_bytes:
                        return await reject()
                except ValueError:
                    pass
        chunks: deque[Any] = deque()
        total = 0
        while True:
            message = await receive()
            if message["type"] == "http.disconnect":
                return
            total += len(message.get("body", b""))
            if total > self.max_bytes:
                return await reject()
            chunks.append(message)
            if not message.get("more_body", False):
                break

        async def replay():
            return chunks.popleft() if chunks else await receive()

        await self.app(scope, replay, send)
