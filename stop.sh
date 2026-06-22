#!/bin/bash
# A股智能分析系统 - 停止服务

PROJECT_DIR="$(cd "$(dirname "$0")" && pwd)"

echo "=== 停止服务 ==="
for port in 8000 5173; do
    if lsof -ti:$port >/dev/null 2>&1; then
        kill $(lsof -ti:$port) 2>/dev/null && echo "端口 $port 进程已停止" || true
    else
        echo "端口 $port 无运行进程"
    fi
done

# 兜底：清掉未绑端口但仍残留的 uvicorn/vite 进程（如启动卡在 lifespan 阶段）
sleep 1
LEFTOVER=$(pgrep -f "uvicorn app.main:app" 2>/dev/null || true)
if [ -n "$LEFTOVER" ]; then
    kill $LEFTOVER 2>/dev/null && echo "清理残留 uvicorn 进程: $LEFTOVER" || true
fi
LEFTOVER_VITE=$(pgrep -f "vite --port 5173" 2>/dev/null || true)
if [ -n "$LEFTOVER_VITE" ]; then
    kill $LEFTOVER_VITE 2>/dev/null && echo "清理残留 vite 进程: $LEFTOVER_VITE" || true
fi
