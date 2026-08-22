#!/usr/bin/env bash
# A股智能分析系统 - 一键启动
# 用法: ./start.sh [dev|prod]
#   dev  - 开发模式（默认，前后端都带热重载）
#   prod - 生产模式（后端无热重载，前端使用 preview）

set -Eeuo pipefail

PROJECT_DIR="$(cd "$(dirname "$0")" && pwd)"
BACKEND_DIR="$PROJECT_DIR/backend"
FRONTEND_DIR="$PROJECT_DIR/frontend"
LOG_DIR="$PROJECT_DIR/logs"
RUN_DIR="$LOG_DIR/run"
MODE="${1:-dev}"

BACKEND_HOST="${BACKEND_HOST:-127.0.0.1}"
BACKEND_PORT="${BACKEND_PORT:-8000}"
FRONTEND_HOST="${FRONTEND_HOST:-127.0.0.1}"
FRONTEND_PORT="${FRONTEND_PORT:-5173}"
STARTUP_TIMEOUT="${STARTUP_TIMEOUT:-90}"

BACKEND_LOG="$LOG_DIR/backend.log"
FRONTEND_LOG="$LOG_DIR/frontend.log"
BACKEND_PID_FILE="$RUN_DIR/backend.pid"
FRONTEND_PID_FILE="$RUN_DIR/frontend.pid"

RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
CYAN='\033[0;36m'
NC='\033[0m'

info()  { printf "%b[INFO]%b %s\n" "$GREEN" "$NC" "$1"; }
warn()  { printf "%b[WARN]%b %s\n" "$YELLOW" "$NC" "$1"; }
error() { printf "%b[ERROR]%b %s\n" "$RED" "$NC" "$1" >&2; }

usage() {
    cat <<EOF
用法: ./start.sh [dev|prod]

可选环境变量:
  BACKEND_HOST      后端监听地址，默认 127.0.0.1
  BACKEND_PORT      后端端口，默认 8000
  FRONTEND_HOST     前端监听地址，默认 127.0.0.1
  FRONTEND_PORT     前端端口，默认 5173
  STARTUP_TIMEOUT   服务启动超时秒数，默认 90
EOF
}

require_command() {
    if ! command -v "$1" >/dev/null 2>&1; then
        error "缺少必要命令: $1"
        exit 1
    fi
}

validate_port() {
    local name="$1"
    local port="$2"
    case "$port" in
        ''|*[!0-9]*)
            error "$name 必须是数字端口: $port"
            exit 1
            ;;
    esac
    if [ "$port" -lt 1 ] || [ "$port" -gt 65535 ]; then
        error "$name 超出有效范围: $port"
        exit 1
    fi
}

listener_pids() {
    lsof -tiTCP:"$1" -sTCP:LISTEN 2>/dev/null | sort -u || true
}

ensure_port_available() {
    local label="$1"
    local port="$2"
    local pids
    pids="$(listener_pids "$port")"
    if [ -z "$pids" ]; then
        return 0
    fi

    error "$label 端口 $port 已被其他进程占用，未自动终止该进程。"
    lsof -nP -iTCP:"$port" -sTCP:LISTEN >&2 || true
    error "请停止占用进程，或通过 ${label}_PORT 指定其他端口。"
    exit 1
}

rotate_log() {
    local log_file="$1"
    if [ -s "$log_file" ]; then
        mv -f "$log_file" "$log_file.prev"
    fi
    : > "$log_file"
}

wait_for_http() {
    local label="$1"
    local url="$2"
    local pid="$3"
    local log_file="$4"
    local waited=0

    while [ "$waited" -lt "$STARTUP_TIMEOUT" ]; do
        if curl -fsS --max-time 2 "$url" >/dev/null 2>&1; then
            info "$label 已就绪（耗时 $((waited + 1))s）"
            return 0
        fi
        if ! kill -0 "$pid" 2>/dev/null; then
            error "$label 进程已退出，请检查日志: $log_file"
            tail -30 "$log_file" >&2 || true
            return 1
        fi
        sleep 1
        waited=$((waited + 1))
    done

    error "$label 在 ${STARTUP_TIMEOUT}s 内未就绪，请检查日志: $log_file"
    tail -30 "$log_file" >&2 || true
    return 1
}

case "$MODE" in
    dev|prod) ;;
    -h|--help)
        usage
        exit 0
        ;;
    *)
        error "未知模式: $MODE，请使用 dev 或 prod"
        usage >&2
        exit 1
        ;;
esac

validate_port BACKEND_PORT "$BACKEND_PORT"
validate_port FRONTEND_PORT "$FRONTEND_PORT"
require_command curl
require_command lsof
require_command npm
require_command uv

if [ ! -d "$BACKEND_DIR/.venv" ]; then
    error "后端依赖未安装，请先运行: ./setup.sh"
    exit 1
fi

if [ ! -d "$FRONTEND_DIR/node_modules" ]; then
    error "前端依赖未安装，请先运行: ./setup.sh"
    exit 1
fi
VITE_BIN="$FRONTEND_DIR/node_modules/.bin/vite"
if [ ! -x "$VITE_BIN" ]; then
    error "Vite 可执行文件不存在，请先运行: ./setup.sh"
    exit 1
fi

if [ ! -f "$PROJECT_DIR/.env" ]; then
    warn ".env 不存在，部分功能可能不可用。运行 cp .env.example .env 创建"
fi

mkdir -p "$LOG_DIR" "$RUN_DIR"

printf "=== 停止当前项目的旧进程 ===\n"
BACKEND_PORT="$BACKEND_PORT" FRONTEND_PORT="$FRONTEND_PORT" \
    "$PROJECT_DIR/stop.sh" --quiet
ensure_port_available BACKEND "$BACKEND_PORT"
ensure_port_available FRONTEND "$FRONTEND_PORT"
rotate_log "$BACKEND_LOG"
rotate_log "$FRONTEND_LOG"

START_COMPLETED=0
cleanup_on_failure() {
    local status=$?
    trap - EXIT
    if [ "$START_COMPLETED" -ne 1 ]; then
        BACKEND_PORT="$BACKEND_PORT" FRONTEND_PORT="$FRONTEND_PORT" \
            "$PROJECT_DIR/stop.sh" --quiet || true
    fi
    exit "$status"
}
trap cleanup_on_failure EXIT

printf "\n=== 启动后端 (FastAPI) [%b%s%b] ===\n" "$CYAN" "$MODE" "$NC"
backend_args=(run --frozen uvicorn app.main:app --host "$BACKEND_HOST" --port "$BACKEND_PORT")
if [ "$MODE" = "dev" ]; then
    backend_args+=(--reload)
fi

(
    cd "$BACKEND_DIR"
    nohup uv "${backend_args[@]}" >> "$BACKEND_LOG" 2>&1 &
    echo "$!" > "$BACKEND_PID_FILE"
)
BACKEND_PID="$(cat "$BACKEND_PID_FILE")"
info "后端 PID: $BACKEND_PID"

BACKEND_CHECK_HOST="$BACKEND_HOST"
case "$BACKEND_CHECK_HOST" in
    0.0.0.0|::|'[::]') BACKEND_CHECK_HOST="127.0.0.1" ;;
esac
BACKEND_URL="http://${BACKEND_CHECK_HOST}:${BACKEND_PORT}"
wait_for_http "后端" "$BACKEND_URL/api/health/ready" "$BACKEND_PID" "$BACKEND_LOG"

printf "\n=== 启动前端 (Vite) [%b%s%b] ===\n" "$CYAN" "$MODE" "$NC"
cd "$FRONTEND_DIR"
if [ "$MODE" = "prod" ] && [ "${SKIP_FRONTEND_BUILD:-0}" != "1" ]; then
    info "正在构建最新前端资源..."
    npm run build
fi

VITE_API_PROXY_TARGET="${VITE_API_PROXY_TARGET:-$BACKEND_URL}"
if [ "$MODE" = "dev" ]; then
    frontend_command=("$VITE_BIN" --host "$FRONTEND_HOST" --port "$FRONTEND_PORT" --strictPort)
else
    frontend_command=("$VITE_BIN" preview --host "$FRONTEND_HOST" --port "$FRONTEND_PORT" --strictPort)
fi
nohup env VITE_API_PROXY_TARGET="$VITE_API_PROXY_TARGET" \
    "${frontend_command[@]}" >> "$FRONTEND_LOG" 2>&1 &
FRONTEND_PID=$!
echo "$FRONTEND_PID" > "$FRONTEND_PID_FILE"
info "前端 PID: $FRONTEND_PID"

FRONTEND_CHECK_HOST="$FRONTEND_HOST"
case "$FRONTEND_CHECK_HOST" in
    0.0.0.0|::|'[::]') FRONTEND_CHECK_HOST="127.0.0.1" ;;
esac
FRONTEND_URL="http://${FRONTEND_CHECK_HOST}:${FRONTEND_PORT}"
wait_for_http "前端" "$FRONTEND_URL/" "$FRONTEND_PID" "$FRONTEND_LOG"

START_COMPLETED=1
trap - EXIT

printf "\n%b=== 启动完成 ===%b\n\n" "$GREEN" "$NC"
printf "  前端:    %s\n" "$FRONTEND_URL"
printf "  后端:    %s\n" "$BACKEND_URL"
printf "  API 文档: %s/docs\n\n" "$BACKEND_URL"
printf "  日志:\n"
printf "    tail -f %s\n" "$BACKEND_LOG"
printf "    tail -f %s\n\n" "$FRONTEND_LOG"
printf "  状态: make status\n"
printf "  停止: ./stop.sh 或 make stop\n"
