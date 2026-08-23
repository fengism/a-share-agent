from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.runtime.middleware import RequestObservabilityMiddleware, UserContextMiddleware


def create_application(
    *,
    lifespan,
    cors_origins: list[str],
) -> FastAPI:
    application = FastAPI(title="A股智能分析系统", version="0.1.0", lifespan=lifespan)
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
