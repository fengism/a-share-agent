"""应用版本解析。

OpenAPI 元数据与在线更新接口必须对"当前是哪个版本"给出一致答案：此前
`app.runtime.app_setup` 会回退读取 pyproject，而 `app.api.version` 只看
`APP_VERSION` 环境变量并默认 `dev`，导致源码部署在页面上被误判成开发环境、
在线更新被直接禁用。这里收敛为唯一来源。
"""

from __future__ import annotations

import os
import tomllib
from pathlib import Path

# backend/pyproject.toml（app/runtime/app_version.py -> backend/）
_PYPROJECT = Path(__file__).resolve().parents[2] / "pyproject.toml"
_FALLBACK_VERSION = "0.1.0"


def resolve_app_version() -> str:
    """返回应用版本。

    优先取构建期或运行期注入的 `APP_VERSION`（CI 按 tag 注入，形如 `v0.6.0`，
    本地 compose 构建默认为 `dev`），保持原样以便调用方决定是否去掉 v 前缀；
    未注入时回退读取 pyproject，使源码部署能报告真实版本。
    """
    env_version = os.environ.get("APP_VERSION", "").strip()
    if env_version:
        return env_version
    try:
        project = tomllib.loads(_PYPROJECT.read_text(encoding="utf-8"))
        return str(project["project"]["version"])
    except (OSError, KeyError, tomllib.TOMLDecodeError):
        # 运行镜像不包含 pyproject.toml，仅在显式清空 APP_VERSION 时才会走到这里。
        return _FALLBACK_VERSION
