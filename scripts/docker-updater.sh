#!/bin/sh
# 在线更新执行器：配合 backend /api/system/update 的更新协议工作。
# 轮询 data/update-request.json（由后端管理员触发时原子写入）；检测到后依次
# 拉取新镜像、仅重建 backend/frontend、等待健康检查，失败时回滚旧镜像。
# 全程状态写入 data/update-status.json 供后端 /api/system/update/status 读取。
#
# 版本口径：请求里的 target_version 是后端从 release marker 解析出的 revision（短 sha），
# 因此这里优先拉取不可变版本 <repo>:sha-<target_version>（该 tag 由发布流水线为后端与
# 前端同时发布），使「提示有新版本」与「实际拉到的镜像」严格对齐，并让版本可复现、可回滚。
# target_version 缺失/非法（兼容旧请求或异常写入）时才回退到浮动的 :main 别名 ——
# :main 只在发版或手动发布时前移，因此它与最近一次发布保持一致。
# 注意：重建时通过环境变量把镜像引用传给 compose，容器会固定指向该 sha；之后从宿主机
# 直接 `docker compose up -d` 会按 .env 回到 :main（内容通常与最近发布一致）。
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
BACKEND_REPO="${UPDATE_BACKEND_IMAGE_REPOSITORY:-fengliu1989/a-share-backend}"
FRONTEND_REPO="${UPDATE_FRONTEND_IMAGE_REPOSITORY:-fengliu1989/a-share-frontend}"

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

# 把 target_version 归一化成可用的镜像 tag 后缀；非法输入返回空串（调用方回退 :main）。
target_tag() {
    _value=$(sed -n 's/.*"target_version"[[:space:]]*:[[:space:]]*"\([^"]*\)".*/\1/p' "$1" 2>/dev/null | head -n 1)
    case "$_value" in
        ''|*[!0-9a-fA-F]*) return 0 ;;
    esac
    # 短 sha 至少 7 位；上限按完整 sha1/sha256 长度放宽
    [ "${#_value}" -ge 7 ] && [ "${#_value}" -le 64 ] && printf 'sha-%s' "$_value"
}

update_once() {
    _target_tag=$(target_tag "$REQUEST")
    mv "$REQUEST" "$RUNNING"

    if [ -n "$_target_tag" ]; then
        BACKEND_IMAGE="$BACKEND_REPO:$_target_tag"
        FRONTEND_IMAGE="$FRONTEND_REPO:$_target_tag"
    else
        BACKEND_IMAGE="$BACKEND_REPO:main"
        FRONTEND_IMAGE="$FRONTEND_REPO:main"
    fi

    write_status "running" "正在拉取新镜像"
    _old_backend_id=$(image_id "$BACKEND_IMAGE")
    _old_frontend_id=$(image_id "$FRONTEND_IMAGE")
    _fallback_note=""

    if ! pull_with_retry "$BACKEND_IMAGE" || ! pull_with_retry "$FRONTEND_IMAGE"; then
        if [ -z "$_target_tag" ]; then
            write_status "failed" "镜像拉取失败（已重试），服务未变更"
            rm -f "$RUNNING"
            return
        fi
        # 目标版本镜像不可用（例如该次发布的镜像已被清理）：回退到 :main 别名，
        # 它只在发版/手动发布时前移，因此仍与最近一次发布对应。
        _fallback_note="（目标版本镜像不可用，已回退 main 别名）"
        BACKEND_IMAGE="$BACKEND_REPO:main"
        FRONTEND_IMAGE="$FRONTEND_REPO:main"
        _old_backend_id=$(image_id "$BACKEND_IMAGE")
        _old_frontend_id=$(image_id "$FRONTEND_IMAGE")
        write_status "running" "目标版本镜像不可用，回退拉取 main 别名"
        if ! pull_with_retry "$BACKEND_IMAGE" || ! pull_with_retry "$FRONTEND_IMAGE"; then
            write_status "failed" "镜像拉取失败（已重试），服务未变更"
            rm -f "$RUNNING"
            return
        fi
    fi

    if [ "$_old_backend_id" = "$(image_id "$BACKEND_IMAGE")" ] \
        && [ "$_old_frontend_id" = "$(image_id "$FRONTEND_IMAGE")" ]; then
        write_status "succeeded" "镜像无变化，已是最新版本${_fallback_note}"
        rm -f "$RUNNING"
        return
    fi

    write_status "running" "正在重建 backend/frontend"
    # 同时用环境变量覆盖 compose 的镜像引用：容器固定到本次拉取的版本，
    # 而不是 .env 里的浮动 :main。
    if ! BACKEND_IMAGE="$BACKEND_IMAGE" FRONTEND_IMAGE="$FRONTEND_IMAGE" \
        docker compose up -d --no-deps --remove-orphans backend frontend; then
        write_status "failed" "服务重建失败"
        rm -f "$RUNNING"
        return
    fi

    if wait_backend_healthy; then
        write_status "succeeded" "已更新到 ${_target_tag:-main}${_fallback_note}"
        rm -f "$RUNNING"
        return
    fi

    write_status "running" "新版本未通过健康检查，正在回滚"
    [ -n "$_old_backend_id" ] && docker tag "$_old_backend_id" "$BACKEND_IMAGE"
    [ -n "$_old_frontend_id" ] && docker tag "$_old_frontend_id" "$FRONTEND_IMAGE"
    if BACKEND_IMAGE="$BACKEND_IMAGE" FRONTEND_IMAGE="$FRONTEND_IMAGE" \
        docker compose up -d --no-deps backend frontend && wait_backend_healthy; then
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
