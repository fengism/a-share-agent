import os
from pathlib import Path

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.runtime.middleware import RequestObservabilityMiddleware, UserContextMiddleware

# 交互式文档与 OpenAPI 描述是应用级端点，不受任何路由依赖保护。
# 未认证访问者可以据此拉取全量路由表、参数 schema 和非直观挂载点。
# 因此默认关闭；本地开发显式用 APP_EXPOSE_DOCS=1 打开。
# sandbox 侧一直是这么做的（sandbox/runner.py 里 docs_url=None）。
_EXPOSE_DOCS = os.getenv("APP_EXPOSE_DOCS", "").strip().lower() in {"1", "true", "yes", "on"}


def _app_version() -> str:
    """应用版本：优先取 CI 注入的 APP_VERSION，其次读 pyproject，最后回退。"""
    env_version = os.environ.get("APP_VERSION", "").strip()
    if env_version:
        return env_version.lstrip("v")
    pyproject = Path(__file__).resolve().parents[2] / "pyproject.toml"
    try:
        import tomllib

        data = tomllib.loads(pyproject.read_text(encoding="utf-8"))
        return str(data["project"]["version"])
    except Exception:
        return "0.1.0"


def create_application(
    *,
    lifespan,
    cors_origins: list[str],
) -> FastAPI:
    application = FastAPI(
        title="A股智能分析系统",
        version=_app_version(),
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
    application.add_middleware(UserContextMiddleware)
    application.add_middleware(RequestObservabilityMiddleware)
    return application
