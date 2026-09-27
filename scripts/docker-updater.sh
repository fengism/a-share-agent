#!/bin/sh
# 在线更新执行器：配合 backend /api/system/update 的更新协议工作。
# 轮询 data/update-request.json（由后端管理员触发时原子写入）；检测到后依次
# 拉取新镜像、仅重建 backend/frontend、等待健康检查，失败时回滚旧镜像。
# 全程状态写入 data/update-status.json 供后端 /api/system/update/status 读取。
#
# 环境变量：
#   HOST_PROJECT_DIR                  项目目录（compose 工作目录，默认 PWD）
#   UPDATE_BACKEND_IMAGE_REPOSITORY   backend 镜像仓库（默认 fengliu1989/a-share-backend）
#   UPDATE_FRONTEND_IMAGE_REPOSITORY  frontend 镜像仓库（默认 fengliu1989/a-share-frontend）
#   UPDATE_POLL_SECONDS               轮询间隔秒数（默认 15）
#   UPDATE_HEALTH_TIMEOUT_SECONDS     重建后健康检查等待上限（默认 240）

set -u

PROJECT_DIR="${HOST_PROJECT_DIR:-$PWD}"
DATA_DIR="$PROJECT_DIR/data"
REQUEST="$DATA_DIR/update-request.json"
RUNNING="$DATA_DIR/update-request.running.json"
STATUS_FILE="$DATA_DIR/update-status.json"
POLL_SECONDS="${UPDATE_POLL_SECONDS:-15}"
HEALTH_TIMEOUT="${UPDATE_HEALTH_TIMEOUT_SECONDS:-240}"
PULL_TIMEOUT_SECONDS="${UPDATE_PULL_TIMEOUT_SECONDS:-900}"
BACKEND_IMAGE="${UPDATE_BACKEND_IMAGE_REPOSITORY:-fengliu1989/a-share-backend}:main"
FRONTEND_IMAGE="${UPDATE_FRONTEND_IMAGE_REPOSITORY:-fengliu1989/a-share-frontend}:main"

now_utc() { date -u +%Y-%m-%dT%H:%M:%SZ; }

write_status() {
    _status="$1"
    _message="$2"
    printf '{"status":"%s","message":"%s","updated_at":"%s"}\n' \
        "$_status" "$_message" "$(now_utc)" > "$STATUS_FILE.tmp.$$" \
        && mv "$STATUS_FILE.tmp.$$" "$STATUS_FILE"
}

image_id() { docker image inspect "$1" --format '{{.Id}}' 2>/dev/null || true; }

# 拉取单个镜像：失败自动重试（网络抖动一重试基本能过），并限制单次拉取时长，
# 避免 Registry 连接挂死占住更新通道。
pull_with_retry() {
    _image="$1"
    _attempt=1
    while [ "$_attempt" -le 3 ]; do
        if timeout "$PULL_TIMEOUT_SECONDS" docker pull "$_image"; then
            return 0
        fi
        _attempt=$((_attempt + 1))
        [ "$_attempt" -le 3 ] && sleep 15
    done
    return 1
}

wait_backend_healthy() {
    _deadline=$(( $(date +%s) + HEALTH_TIMEOUT ))
    while [ "$(date +%s)" -lt "$_deadline" ]; do
        _cid=$(docker compose ps -q backend 2>/dev/null)
        if [ -n "$_cid" ] \
            && [ "$(docker inspect -f '{{.State.Health.Status}}' "$_cid" 2>/dev/null)" = "healthy" ]; then
            return 0
        fi
        sleep 5
    done
    return 1
}

update_once() {
    _target=$(sed -n 's/.*"target_version"[[:space:]]*:[[:space:]]*"\([^"]*\)".*/\1/p' "$REQUEST" 2>/dev/null)
    mv "$REQUEST" "$RUNNING"

    write_status "running" "正在拉取新镜像"
    _old_backend_id=$(image_id "$BACKEND_IMAGE")
    _old_frontend_id=$(image_id "$FRONTEND_IMAGE")

    if ! pull_with_retry "$BACKEND_IMAGE" || ! pull_with_retry "$FRONTEND_IMAGE"; then
        write_status "failed" "镜像拉取失败（已重试），服务未变更"
        rm -f "$RUNNING"
        return
    fi

    if [ "$_old_backend_id" = "$(image_id "$BACKEND_IMAGE")" ] \
        && [ "$_old_frontend_id" = "$(image_id "$FRONTEND_IMAGE")" ]; then
        write_status "succeeded" "镜像无变化，已是最新版本"
        rm -f "$RUNNING"
        return
    fi

    write_status "running" "正在重建 backend/frontend"
    if ! docker compose up -d --no-deps --remove-orphans backend frontend; then
        write_status "failed" "服务重建失败"
        rm -f "$RUNNING"
        return
    fi

    if wait_backend_healthy; then
        write_status "succeeded" "已更新${_target:+到 ${_target}}"
        rm -f "$RUNNING"
        return
    fi

    write_status "running" "新版本未通过健康检查，正在回滚"
    [ -n "$_old_backend_id" ] && docker tag "$_old_backend_id" "$BACKEND_IMAGE"
    [ -n "$_old_frontend_id" ] && docker tag "$_old_frontend_id" "$FRONTEND_IMAGE"
    if docker compose up -d --no-deps backend frontend && wait_backend_healthy; then
        write_status "failed_rolled_back" "更新失败，已回滚到旧版本"
    else
        write_status "failed_rollback_failed" "更新失败且回滚未恢复健康，请人工介入"
    fi
    rm -f "$RUNNING"
}

while true; do
    if [ -f "$REQUEST" ] && [ ! -f "$RUNNING" ]; then
        update_once || write_status "failed" "更新过程异常终止"
        rm -f "$RUNNING"
    fi
    sleep "$POLL_SECONDS"
done
