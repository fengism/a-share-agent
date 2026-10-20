"""MiniRacer 兜底 guard：覆盖范围不变，且不再给每次进程退出加 43ms。

历史：guard 注册在 ``app/__init__.py``，于是
1. 任何 ``import app.*``（含可独立抽取的 agentic 核心）都拖进 ``app.infrastructure``；
2. 每次解释器退出都要 import ``py_mini_racer``（V8 二进制，~43ms）才能判断是否需要打补丁，
   即使这个进程从未碰过 AkShare。
"""

from __future__ import annotations

import sys
import types

import pytest

from app.infrastructure import javascript_runtime


def test_guard_does_not_import_py_mini_racer_when_it_was_never_used(monkeypatch):
    monkeypatch.delitem(sys.modules, "py_mini_racer", raising=False)
    javascript_runtime.install_legacy_mini_racer_shutdown_guard()
    assert "py_mini_racer" not in sys.modules, (
        "py_mini_racer 从未被导入时不可能存在实例，退出阶段不该为判断而加载 V8"
    )


def test_guard_patches_a_legacy_class_when_loaded(monkeypatch):
    class LegacyMiniRacer:
        def __del__(self):  # pragma: no cover - replaced by the guard
            raise AttributeError("simulated legacy teardown race")

    LegacyMiniRacer.__module__ = "py_mini_racer.py_mini_racer"
    fake = types.ModuleType("py_mini_racer")
    fake.MiniRacer = LegacyMiniRacer  # type: ignore[attr-defined]
    monkeypatch.setitem(sys.modules, "py_mini_racer", fake)

    javascript_runtime.install_legacy_mini_racer_shutdown_guard()

    assert getattr(LegacyMiniRacer.__del__, javascript_runtime._DESTRUCTOR_GUARD_MARKER, False)
    # 打了补丁之后，解释器退出期的 AttributeError 不再冒出来。
    LegacyMiniRacer().__del__()


def test_modern_mini_racer_is_left_alone(monkeypatch):
    class ModernMiniRacer:
        def __del__(self):
            raise AssertionError("不该被 guard 替换")

    ModernMiniRacer.__module__ = "py_mini_racer._mini_racer"
    fake = types.ModuleType("py_mini_racer")
    fake.MiniRacer = ModernMiniRacer  # type: ignore[attr-defined]
    monkeypatch.setitem(sys.modules, "py_mini_racer", fake)

    javascript_runtime.install_legacy_mini_racer_shutdown_guard()

    # 直接调函数，避免创建实例后 GC 时再抛一次（unraisable warning）。
    with pytest.raises(AssertionError):
        ModernMiniRacer.__del__(types.SimpleNamespace())


def test_register_is_idempotent(monkeypatch):
    registered: list[object] = []
    monkeypatch.setattr(javascript_runtime.atexit, "register", registered.append)
    monkeypatch.setattr(javascript_runtime, "_fallback_registered", False)

    javascript_runtime.register_shutdown_guard_fallback()
    javascript_runtime.register_shutdown_guard_fallback()
    javascript_runtime.register_shutdown_guard_fallback()

    assert registered == [javascript_runtime.install_legacy_mini_racer_shutdown_guard]


def test_akshare_provider_registers_the_fallback():
    """guard 必须挂在真正 import akshare 的地方，否则兜底会失效。"""
    import importlib

    module = importlib.import_module("app.infrastructure.providers.akshare")
    assert module is not None
    assert javascript_runtime._fallback_registered is True
