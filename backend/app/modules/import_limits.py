"""主数据上传统一限制：50 MiB 文件，Base64 JSON 请求预留至 70 MiB。"""

MAX_IMPORT_FILE_BYTES = 50 * 1024 * 1024
MAX_IMPORT_BASE64_CHARS = 4 * ((MAX_IMPORT_FILE_BYTES + 2) // 3)
MAX_IMPORT_REQUEST_BYTES = 70 * 1024 * 1024
IMPORT_PATHS = frozenset({
    "/api/stock-profile/records/import",
    "/api/stock-concept/import/preview", "/api/stock-concept/import/commit",
    "/api/industry-classification/import/preview", "/api/industry-classification/import/commit",
})
