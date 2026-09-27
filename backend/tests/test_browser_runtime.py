"""浏览器运行时库路径策略测试。"""

import os

from app.infrastructure.browser_runtime import (
    _build_browser_env,
    _merge_library_paths,
    ensure_browser_library_paths,
)


def test_merge_library_paths_prepends_new_dirs():
    assert _merge_library_paths("/existing", ["/a", "/b"]) == "/a:/b:/existing"


def test_merge_library_paths_skips_duplicates():
    assert _merge_library_paths("/a:/existing", ["/a", "/b"]) == "/b:/a:/existing"


def test_merge_library_paths_noop_when_all_present():
    assert _merge_library_paths("/a:/b", ["/a", "/b"]) is None


def test_ensure_browser_library_paths_updates_process_env(monkeypatch):
    monkeypatch.setattr("app.infrastructure.browser_runtime._extra_library_dirs", lambda: ["/extra-libs"])
    monkeypatch.setenv("LD_LIBRARY_PATH", "/existing")

    ensure_browser_library_paths()
    assert os.environ["LD_LIBRARY_PATH"] == "/extra-libs:/existing"

    # 幂等：重复调用不产生重复目录
    ensure_browser_library_paths()
    assert os.environ["LD_LIBRARY_PATH"] == "/extra-libs:/existing"


def test_ensure_browser_library_paths_noop_without_candidates(monkeypatch):
    monkeypatch.setattr("app.infrastructure.browser_runtime._extra_library_dirs", lambda: [])
    monkeypatch.delenv("LD_LIBRARY_PATH", raising=False)

    ensure_browser_library_paths()
    assert "LD_LIBRARY_PATH" not in os.environ


def test_build_browser_env_merges_process_env_custom_env_and_library_paths(monkeypatch):
    monkeypatch.setattr("app.infrastructure.browser_runtime._extra_library_dirs", lambda: ["/extra-libs"])
    monkeypatch.setenv("BACKEND_VAR", "x")

    env = _build_browser_env({"PROXY": "1"})
    assert env["BACKEND_VAR"] == "x"
    assert env["PROXY"] == "1"
    assert env["LD_LIBRARY_PATH"] == "/extra-libs"
