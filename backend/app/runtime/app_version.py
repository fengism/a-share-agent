"""应用版本解析。

OpenAPI 元数据与在线更新接口必须对"当前是哪个版本"给出一致答案：此前
`app.runtime.app_setup` 会回退读取 pyproject，而 `app.api.version` 只看
`APP_VERSION` 环境变量并默认 `dev`，导致源码部署在页面上被误判成开发环境、
在线更新被直接禁用。这里收敛为唯一来源。
"""

from __future__ import annotations

import os
import subprocess
import tomllib
from functools import lru_cache
from pathlib import Path

# backend/pyproject.toml（app/runtime/app_version.py -> backend/）
_PYPROJECT = Path(__file__).resolve().parents[2] / "pyproject.toml"
_FALLBACK_VERSION = "0.1.0"


@lru_cache(maxsize=1)
def resolve_app_version() -> str:
    """返回应用版本。

    1. 优先取构建期或运行期注入的 `APP_VERSION`（CI 发版按 tag 注入，形如 `v0.7.2`，
       本地 compose 构建默认为 `dev`）；
    2. 未注入时（如本地源码直接运行），尝试通过 `git describe` 动态解析当前仓库最近的 Tag；
    3. 无法获取有效 git tag 时（如开发中或压缩包部署），回退读取 pyproject.toml 声明或兜底默认值。
    """
    env_version = os.environ.get("APP_VERSION", "").strip()
    if env_version:
        return env_version

    # 尝试从 git 标签解析
    try:
        git_desc = subprocess.check_output(
            ["git", "describe", "--tags", "--match", "v*", "--always"],
            stderr=subprocess.DEVNULL,
            text=True,
            cwd=_PYPROJECT.parent,
        ).strip()
        if git_desc and (git_desc.startswith("v") or "." in git_desc):
            return git_desc
    except (OSError, subprocess.SubprocessError):
        pass

    try:
        project = tomllib.loads(_PYPROJECT.read_text(encoding="utf-8"))
        return str(project["project"]["version"])
    except (OSError, KeyError, tomllib.TOMLDecodeError):
        # 运行镜像不包含 pyproject.toml，仅在显式清空 APP_VERSION 时才会走到这里。
        return _FALLBACK_VERSION
