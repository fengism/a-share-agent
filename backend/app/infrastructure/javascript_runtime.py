"""Process-wide initialization for the JavaScript runtime used by AkShare."""

from __future__ import annotations

import logging
import threading
from typing import Any

logger = logging.getLogger(__name__)

_INITIALIZATION_EXPRESSION = "1 + 1"
_INITIALIZATION_RESULT = 2
_DESTRUCTOR_GUARD_MARKER = "__a_share_agent_safe_destructor__"

_initialization_lock = threading.Lock()
_initialized = False


def _load_mini_racer() -> tuple[type[Any], bool]:
    """Load the platform-selected MiniRacer and report whether it is legacy."""
    try:
        from py_mini_racer import MiniRacer
    except ImportError as exc:  # pragma: no cover - AkShare declares this dependency
        raise RuntimeError("MiniRacer 不可用，无法初始化 AkShare JavaScript 运行时") from exc

    is_legacy = MiniRacer.__module__.endswith(".py_mini_racer")
    return MiniRacer, is_legacy


def _install_legacy_destructor_guard(mini_racer_class: type[Any]) -> None:
    """Make py-mini-racer 0.6 cleanup safe during interpreter shutdown."""
    original_destructor = getattr(mini_racer_class, "__del__", None)
    if original_destructor is None or getattr(
        original_destructor,
        _DESTRUCTOR_GUARD_MARKER,
        False,
    ):
        return

    def safe_destructor(self: Any) -> None:
        if getattr(self, "ext", None) is None:
            return
        try:
            original_destructor(self)
        except (AttributeError, TypeError):
            # Module globals and native handles can already be cleared by Python.
            return

    setattr(safe_destructor, _DESTRUCTOR_GUARD_MARKER, True)
    mini_racer_class.__del__ = safe_destructor


def install_legacy_mini_racer_shutdown_guard() -> None:
    """Best-effort fallback for processes that do not run the app lifespan."""
    try:
        mini_racer_class, is_legacy = _load_mini_racer()
    except RuntimeError:
        return
    if is_legacy:
        _install_legacy_destructor_guard(mini_racer_class)


def initialize_javascript_runtime() -> None:
    """Initialize V8 once before application threads can create contexts.

    MiniRacer's first V8 initialization is process-global. Some macOS releases
    can abort the process when multiple threads perform that first
    initialization concurrently. FastAPI calls this synchronously at startup,
    before the shared blocking executor and background tasks are started.
    """
    global _initialized

    if _initialized:
        return

    with _initialization_lock:
        if _initialized:
            return

        mini_racer_class, is_legacy = _load_mini_racer()
        if is_legacy:
            _install_legacy_destructor_guard(mini_racer_class)

        runtime = mini_racer_class()
        try:
            result = runtime.eval(_INITIALIZATION_EXPRESSION)
            if result != _INITIALIZATION_RESULT:
                raise RuntimeError(
                    f"MiniRacer 自检结果异常: expected={_INITIALIZATION_RESULT}, actual={result!r}"
                )
        finally:
            close = getattr(runtime, "close", None)
            if callable(close):
                close()

        _initialized = True
        logger.info(
            "MiniRacer JavaScript 运行时初始化完成 implementation=%s",
            "legacy" if is_legacy else "modern",
        )
