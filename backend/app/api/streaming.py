"""流式 HTTP 响应的 OpenAPI 契约。"""

SSE_RESPONSES = {
    200: {
        "description": "Server-Sent Events stream",
        "content": {
            "text/event-stream": {
                "schema": {"type": "string"},
            },
        },
    },
}
