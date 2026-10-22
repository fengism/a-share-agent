from __future__ import annotations

import os
from unittest.mock import patch

from packaging.version import Version

from app.api.version import _is_newer_release, _parse_semantic_version
from app.runtime.app_version import resolve_app_version


def test_parse_semantic_version_standard():
    assert _parse_semantic_version("0.7.1") == Version("0.7.1")
    assert _parse_semantic_version("v0.7.1") == Version("0.7.1")
    assert _parse_semantic_version("V1.2.3") == Version("1.2.3")
    assert _parse_semantic_version("  v0.8.0-rc1 ") == Version("0.8.0rc1")


def test_parse_semantic_version_git_describe():
    # 针对 git describe 输出提取基础版本
    assert _parse_semantic_version("v0.7.1-14-g7a6df6") == Version("0.7.1")
    assert _parse_semantic_version("0.8.0-1-g1234567") == Version("0.8.0")


def test_parse_semantic_version_invalid():
    assert _parse_semantic_version("") is None
    assert _parse_semantic_version("dev") is None
    assert _parse_semantic_version("invalid-string") is None


def test_is_newer_release():
    assert _is_newer_release("v0.7.1", "v0.7.2") is True
    assert _is_newer_release("v0.7.1", "v0.8.0") is True
    assert _is_newer_release("v0.7.1-14-g7a6df6", "v0.8.0") is True
    assert _is_newer_release("v0.7.2", "v0.7.1") is False
    assert _is_newer_release("v0.7.1", "v0.7.1") is False
    assert _is_newer_release("dev", "v0.8.0") is False


def test_resolve_app_version_from_env():
    resolve_app_version.cache_clear()
    with patch.dict(os.environ, {"APP_VERSION": "v1.0.0"}):
        assert resolve_app_version() == "v1.0.0"
    resolve_app_version.cache_clear()
