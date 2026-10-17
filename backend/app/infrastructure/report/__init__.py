"""报表渲染共享设施。

个股分析、产业链与每日复盘三个模块都需要把结构化数据渲染成 HTML/SVG 报表，
再导出 PDF 或截图推送。原先三处各自实现了浏览器启动、截图、转义等样板逻辑，
这里收敛为可复用组件，避免策略再次漂移。

当前包含：
- :mod:`app.infrastructure.report.browser` —— 同步 Playwright 元素截图
"""

from __future__ import annotations

from app.infrastructure.report.browser import (
    DEFAULT_DEVICE_SCALE_FACTOR,
    render_elements_to_pngs,
)

__all__ = [
    "DEFAULT_DEVICE_SCALE_FACTOR",
    "render_elements_to_pngs",
]
