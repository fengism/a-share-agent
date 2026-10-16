"""仓库目录定位（不依赖 Settings，避免分组模块与 schema 循环导入）。"""

from __future__ import annotations

from pathlib import Path

BACKEND_DIR = Path(__file__).resolve().parents[2]
ROOT_DIR = BACKEND_DIR.parent
