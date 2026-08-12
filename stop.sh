#!/usr/bin/env bash
# A股智能分析系统 - 安全停止当前项目服务

set -u

PROJECT_DIR="$(cd "$(dirname "$0")" && pwd)"
BACKEND_DIR="$PROJECT_DIR/backend"
FRONTEND_DIR="$PROJECT_DIR/frontend"
RUN_DIR="$PROJECT_DIR/logs/run"

BACKEND_PORT="${BACKEND_PORT:-8090}"
FRONTEND_PORT="${FRONTEND_PORT:-5173}"
STOP_TIMEOUT="${STOP_TIMEOUT:-15}"
QUIET=0

if [ "${1:-}" = "--quiet" ]; then
    QUIET=1
elif [ -n "${1:-}" ]; then
    printf "用法: ./stop.sh [--quiet]\n" >&2
    exit 1
fi

info() {
    if [ "$QUIET" -ne 1 ]; then
        printf "[INFO] %s\n" "$1"
    fi
    return 0
}

warn() {
    printf "[WARN] %s\n" "$1" >&2
}

listener_pids() {
    lsof -tiTCP:"$1" -sTCP:LISTEN 2>/dev/null | sort -u || true
}

backend_candidate_pids() {
    if ! command -v pgrep >/dev/null 2>&1; then
        return 0
    fi
    {
        pgrep -f 'uvicorn[[:space:]]+app\.main:app' 2>/dev/null || true
        pgrep -f 'multiprocessing\.spawn.*spawn_main' 2>/dev/null || true
    } | sort -u
}

process_cwd() {
    lsof -a -p "$1" -d cwd -Fn 2>/dev/null | sed -n 's/^n//p' | head -1
}

process_command() {
    ps -p "$1" -o command= 2>/dev/null || true
}

pid_belongs_to_service() {
    local pid="$1"
    local expected_dir="$2"
    local service="$3"
    local cwd
    local command

    cwd="$(process_cwd "$pid")"
    case "$cwd" in
        "$expected_dir"|"$expected_dir"/*) ;;
        *) return 1 ;;
    esac

    command="$(process_command "$pid")"
    if [ -z "$command" ]; then
        return 0
    fi
    case "$service:$command" in
        backend:*uvicorn*app.main:app*) return 0 ;;
        backend:*multiprocessing.spawn*spawn_main*) return 0 ;;
        frontend:*vite*) return 0 ;;
        frontend:*npm*run*dev*) return 0 ;;
        frontend:*npm*run*preview*) return 0 ;;
        *) return 1 ;;
    esac
}

wait_for_pid_exit() {
    local pid="$1"
    local waited=0
    while kill -0 "$pid" 2>/dev/null; do
        if [ "$waited" -ge "$STOP_TIMEOUT" ]; then
            return 1
        fi
        sleep 1
        waited=$((waited + 1))
    done
    return 0
}

terminate_pid() {
    local pid="$1"
    local label="$2"
    local expected_dir="$3"
    local service="$4"

    if ! kill -0 "$pid" 2>/dev/null; then
        return 0
    fi
    if ! pid_belongs_to_service "$pid" "$expected_dir" "$service"; then
        warn "$label PID $pid 不属于当前项目，已跳过。"
        return 1
    fi

    kill "$pid" 2>/dev/null || true
    if wait_for_pid_exit "$pid"; then
        info "$label PID $pid 已停止"
        return 0
    fi

    warn "$label PID $pid 未在 ${STOP_TIMEOUT}s 内退出，发送 SIGKILL。"
    kill -KILL "$pid" 2>/dev/null || true
    wait_for_pid_exit "$pid" || true
}

stop_service() {
    local service="$1"
    local label="$2"
    local port="$3"
    local expected_dir="$4"
    local pid_file="$RUN_DIR/$service.pid"
    local pid
    local pids
    local remaining

    if [ -f "$pid_file" ]; then
        pid="$(sed -n '1p' "$pid_file" 2>/dev/null || true)"
        case "$pid" in
            ''|*[!0-9]*) ;;
            *) terminate_pid "$pid" "$label" "$expected_dir" "$service" || true ;;
        esac
        rm -f "$pid_file"
    fi

    if [ "$service" = "backend" ]; then
        pids="$(backend_candidate_pids)"
        for pid in $pids; do
            if pid_belongs_to_service "$pid" "$expected_dir" "$service"; then
                terminate_pid "$pid" "$label reload 子进程" "$expected_dir" "$service" || true
            fi
        done
    fi

    pids="$(listener_pids "$port")"
    for pid in $pids; do
        if pid_belongs_to_service "$pid" "$expected_dir" "$service"; then
            terminate_pid "$pid" "$label" "$expected_dir" "$service" || true
        else
            warn "$label 端口 $port 由外部 PID $pid 占用，未自动终止。"
        fi
    done

    remaining="$(listener_pids "$port")"
    if [ -z "$remaining" ]; then
        info "$label 已停止，端口 $port 可用"
    else
        warn "$label 端口 $port 仍被占用，请检查: lsof -nP -iTCP:$port -sTCP:LISTEN"
    fi
}

if ! command -v lsof >/dev/null 2>&1; then
    printf "[ERROR] 缺少必要命令: lsof\n" >&2
    exit 1
fi

if [ "$QUIET" -ne 1 ]; then
    printf "=== 停止当前项目服务 ===\n"
fi

stop_service backend "后端" "$BACKEND_PORT" "$BACKEND_DIR"
stop_service frontend "前端" "$FRONTEND_PORT" "$FRONTEND_DIR"
