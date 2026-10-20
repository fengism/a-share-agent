"""AkShare 数据源实现。"""

from app.infrastructure.javascript_runtime import register_shutdown_guard_fallback

# MiniRacer 的 legacy 析构器在解释器退出时会抛 AttributeError/TypeError。兜底 guard
# 必须挂在真正 import akshare 的地方，而不是 ``app/__init__.py``——后者会让核心包
# 永久依赖宿主基础设施。
register_shutdown_guard_fallback()
