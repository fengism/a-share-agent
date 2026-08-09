#!/usr/bin/env bash
# A股智能分析系统 - 一键安装
# 首次使用或依赖变更时运行

set -Eeuo pipefail

PROJECT_DIR="$(cd "$(dirname "$0")" && pwd)"
BACKEND_DIR="$PROJECT_DIR/backend"
FRONTEND_DIR="$PROJECT_DIR/frontend"

RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m'

info()  { echo -e "${GREEN}[INFO]${NC} $1"; }
warn()  { echo -e "${YELLOW}[WARN]${NC} $1"; }
error() { echo -e "${RED}[ERROR]${NC} $1"; }

# ── 检查前置依赖 ──

check_command() {
    if command -v "$1" >/dev/null 2>&1; then
        local version=$("$1" --version 2>/dev/null | head -1)
        info "$1 已安装: $version"
        return 0
    else
        error "$1 未安装"
        return 1
    fi
}

echo "=== 检查前置依赖 ==="
missing=0

if ! check_command python3; then missing=1; fi
if ! check_command node; then missing=1; fi
if ! check_command npm; then missing=1; fi

if command -v uv >/dev/null 2>&1; then
    info "uv 已安装: $(uv --version)"
else
    warn "uv 未安装，正在安装..."
    if ! command -v curl >/dev/null 2>&1; then
        error "缺少 curl，无法自动安装 uv"
        exit 1
    fi
    curl -LsSf https://astral.sh/uv/install.sh | sh
    export PATH="$HOME/.local/bin:$PATH"
    if command -v uv >/dev/null 2>&1; then
        info "uv 安装成功: $(uv --version)"
    else
        error "uv 安装失败，请手动安装: https://docs.astral.sh/uv/"
        missing=1
    fi
fi

if [ "$missing" -eq 1 ]; then
    error "缺少必要依赖，请安装后重新运行"
    exit 1
fi

echo ""

# ── 检查 .env ──

if [ ! -f "$PROJECT_DIR/.env" ]; then
    if [ -f "$PROJECT_DIR/.env.example" ]; then
        cp "$PROJECT_DIR/.env.example" "$PROJECT_DIR/.env"
        warn "已从 .env.example 创建 .env，请编辑 .env 填入 API Key 等配置"
    else
        warn ".env 文件不存在，请手动创建"
    fi
else
    info ".env 已存在"
fi

echo ""

# ── 安装后端依赖 ──

echo "=== 安装后端依赖 ==="
cd "$BACKEND_DIR"
uv sync --frozen
info "后端依赖安装完成"

echo ""

# ── 安装前端依赖 ──

echo "=== 安装前端依赖 ==="
cd "$FRONTEND_DIR"
if [ -f package-lock.json ]; then
    npm ci
else
    npm install
fi
info "前端依赖安装完成"

echo ""
echo -e "${GREEN}=== 安装完成 ===${NC}"
echo "运行 ./start.sh 启动服务"
