# syntax=docker/dockerfile:1.7

FROM python:3.11-slim AS build

COPY --from=ghcr.io/astral-sh/uv:0.9.1 /uv /uvx /bin/

ENV PYTHONDONTWRITEBYTECODE=1 \
    UV_LINK_MODE=copy

WORKDIR /app

COPY pyproject.toml uv.lock ./
RUN --mount=type=cache,target=/root/.cache/uv \
    uv sync --frozen --no-dev --no-install-project

FROM python:3.11-slim AS runtime

ARG APP_UID=1000
ARG APP_GID=1000
# 展示版本与代码 revision 由 CI 构建参数注入；ARG 必须先于 ENV 声明才能被引用
ARG APP_VERSION=dev
ARG APP_REVISION=dev

# HOME 指向 data 卷挂载点：tdxhub 等库的 ~/.tdxhub 缓存随卷持久化，
# 且 /app/data 由部署侧挂载宿主机目录，规避镜像内目录被挂载遮蔽的问题。
ENV HOME=/app/data/home \
    PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PLAYWRIGHT_BROWSERS_PATH=/ms-playwright \
    APP_VERSION=${APP_VERSION} \
    APP_REVISION=${APP_REVISION} \
    PATH="/app/.venv/bin:$PATH"

WORKDIR /app

RUN groupadd --gid "${APP_GID}" app \
    && useradd --uid "${APP_UID}" --gid app --create-home --home-dir /home/app app

COPY --chown=app:app --from=build /app/.venv /app/.venv

RUN /app/.venv/bin/patchright install --with-deps chromium \
    && chown -R app:app /ms-playwright

COPY --chown=app:app app/ app/
# 空库首次初始化时自动播种概念/个股基础数据，SEEDS_DIR 解析为 /app/seeds
COPY --chown=app:app seeds/ seeds/

RUN mkdir -p data logs && chown -R app:app data logs

USER app

EXPOSE 8000

CMD ["python", "-m", "uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000"]
