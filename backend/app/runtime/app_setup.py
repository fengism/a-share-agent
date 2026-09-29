import os

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.runtime.app_version import resolve_app_version
from app.runtime.import_body_limit import ImportBodyLimitMiddleware
from app.runtime.middleware import RequestObservabilityMiddleware, UserContextMiddleware

# 交互式文档与 OpenAPI 描述是应用级端点，不受任何路由依赖保护。
# 未认证访问者可以据此拉取全量路由表、参数 schema 和非直观挂载点。
# 因此默认关闭；本地开发显式用 APP_EXPOSE_DOCS=1 打开。
# sandbox 侧一直是这么做的（sandbox/runner.py 里 docs_url=None）。
_EXPOSE_DOCS = os.getenv("APP_EXPOSE_DOCS", "").strip().lower() in {"1", "true", "yes", "on"}


def create_application(
    *,
    lifespan,
    cors_origins: list[str],
) -> FastAPI:
    application = FastAPI(
        title="A股智能分析系统",
        version=resolve_app_version().lstrip("v"),
        lifespan=lifespan,
        docs_url="/docs" if _EXPOSE_DOCS else None,
        redoc_url="/redoc" if _EXPOSE_DOCS else None,
        openapi_url="/openapi.json" if _EXPOSE_DOCS else None,
    )
    application.add_middleware(
        CORSMiddleware,
        allow_origins=cors_origins,
        allow_credentials=True,
        allow_methods=["GET", "POST", "PUT", "PATCH", "DELETE", "OPTIONS"],
        allow_headers=["Content-Type", "Authorization", "X-CSRF-Token"],
    )
    application.add_middleware(ImportBodyLimitMiddleware)
    application.add_middleware(UserContextMiddleware)
    application.add_middleware(RequestObservabilityMiddleware)
    return application
