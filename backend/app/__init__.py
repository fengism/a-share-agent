"""A-share agent backend package.

刻意保持为空：任何 ``import app.*``（包括可独立抽取的 ``app.agentic`` 核心）都不应该
在这里被迫加载宿主基础设施。此前这里 import 了
``app.infrastructure.javascript_runtime`` 并注册 MiniRacer 的 atexit 兜底 guard，
导致核心包永远拖进 ``app.infrastructure``。

guard 现在挂在真正 import akshare 的数据源包上
（``app.infrastructure.providers.akshare`` / ``sina.hk``），覆盖面不变；
且 ``install_legacy_mini_racer_shutdown_guard`` 在 ``py_mini_racer`` 从未被导入时
直接返回，避免进程退出时为一次判断加载 43ms 的 V8 二进制。
"""
