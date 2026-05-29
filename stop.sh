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
