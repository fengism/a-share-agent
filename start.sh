#!/bin/bash
# A股智能分析系统 - 一键启动
# 用法: ./start.sh [dev|prod]
#   dev  - 开发模式（默认，前后端都带热重载）
#   prod - 生产模式（后端无 --reload，前端用 preview）

set -e

PROJECT_DIR="$(cd "$(dirname "$0")" && pwd)"
BACKEND_DIR="$PROJECT_DIR/backend"
FRONTEND_DIR="$PROJECT_DIR/frontend"
LOG_DIR="$PROJECT_DIR/logs"
MODE="${1:-dev}"

RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
CYAN='\033[0;36m'
NC='\033[0m'

info()  { echo -e "${GREEN}[INFO]${NC} $1"; }
warn()  { echo -e "${YELLOW}[WARN]${NC} $1"; }
error() { echo -e "${RED}[ERROR]${NC} $1"; }

# ── 前置检查 ──

if [ ! -d "$BACKEND_DIR/.venv" ]; then
    error "后端依赖未安装，请先运行: ./setup.sh"
    exit 1
fi

if [ ! -d "$FRONTEND_DIR/node_modules" ]; then
    error "前端依赖未安装，请先运行: ./setup.sh"
    exit 1
fi

if [ ! -f "$PROJECT_DIR/.env" ]; then
    warn ".env 不存在，部分功能可能不可用。运行 cp .env.example .env 创建"
fi

mkdir -p "$LOG_DIR"

# ── 停止旧进程 ──

echo "=== 停止旧进程 ==="
for port in 8000 5173; do
    if lsof -ti:$port >/dev/null 2>&1; then
        kill $(lsof -ti:$port) 2>/dev/null && info "端口 $port 进程已停止" || true
        sleep 1
    fi
done

echo ""

# ── 启动后端 ──

echo -e "=== 启动后端 (FastAPI) [${CYAN}${MODE}${NC}] ==="
cd "$BACKEND_DIR"

case "$MODE" in
    dev)
        nohup .venv/bin/uvicorn app.main:app --reload --port 8000 >> "$LOG_DIR/backend.log" 2>&1 &
        ;;
    prod)
        nohup .venv/bin/uvicorn app.main:app --port 8000 >> "$LOG_DIR/backend.log" 2>&1 &
        ;;
    *)
        error "未知模式: $MODE，请使用 dev 或 prod"
        exit 1
        ;;
esac

BACKEND_PID=$!
info "后端 PID: $BACKEND_PID"

# 等待后端就绪
for i in $(seq 1 15); do
    if curl -sf http://127.0.0.1:8000/api/health >/dev/null 2>&1; then
        info "后端就绪"
        break
    fi
    if [ "$i" -eq 15 ]; then
        error "后端启动超时，请检查日志: $LOG_DIR/backend.log"
        tail -20 "$LOG_DIR/backend.log"
        exit 1
    fi
    sleep 1
done

echo ""

# ── 启动前端 ──

echo -e "=== 启动前端 (Vite) [${CYAN}${MODE}${NC}] ==="
cd "$FRONTEND_DIR"

case "$MODE" in
    dev)
        nohup npx vite --port 5173 >> "$LOG_DIR/frontend.log" 2>&1 &
        ;;
    prod)
        if [ ! -d "$FRONTEND_DIR/dist" ]; then
            info "前端未构建，正在构建..."
            npm run build
        fi
        nohup npx vite preview --port 5173 >> "$LOG_DIR/frontend.log" 2>&1 &
        ;;
esac

FRONTEND_PID=$!
info "前端 PID: $FRONTEND_PID"

sleep 2
echo ""
echo -e "${GREEN}=== 启动完成 ===${NC}"
echo ""
echo "  前端:   http://localhost:5173"
echo "  后端:   http://127.0.0.1:8000"
echo "  API文档: http://127.0.0.1:8000/docs"
echo ""
echo "  日志:"
echo "    tail -f $LOG_DIR/backend.log"
echo "    tail -f $LOG_DIR/frontend.log"
echo ""
echo "  停止服务: ./stop.sh  或  kill $BACKEND_PID $FRONTEND_PID"
