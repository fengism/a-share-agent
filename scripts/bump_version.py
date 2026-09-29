#!/usr/bin/env python3
"""一键同步项目版本号。

版本号分散在前后端清单与 OpenAPI 产物里，手工修改容易漏改。这里以
``backend/pyproject.toml`` 为唯一事实来源，统一改写其余文件并重新生成
OpenAPI 产物。

用法::

    python3 scripts/bump_version.py 0.6.0     # 指定版本（可带 v 前缀）
    python3 scripts/bump_version.py minor     # 0.5.0 -> 0.6.0
    python3 scripts/bump_version.py patch     # 0.5.0 -> 0.5.1
    python3 scripts/bump_version.py major     # 0.5.0 -> 1.0.0
    python3 scripts/bump_version.py --check   # 只校验一致性，不改文件（CI 用）
    python3 scripts/bump_version.py 0.6.0 --dry-run
    python3 scripts/bump_version.py 0.6.0 --no-codegen
"""

from __future__ import annotations

import argparse
import json
import re
import shutil
import subprocess
import sys
import tomllib
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
PYPROJECT = ROOT / "backend" / "pyproject.toml"
UV_LOCK = ROOT / "backend" / "uv.lock"
BACKEND_PACKAGE = "stock-agent-backend"
PACKAGE_JSON = ROOT / "frontend" / "package.json"
PACKAGE_LOCK = ROOT / "frontend" / "package-lock.json"
OPENAPI_JSON = ROOT / "frontend" / "src" / "api" / "generated" / "openapi.json"

# 与 CI 的 tag 校验保持一致：v?MAJOR.MINOR.PATCH，可选预发布后缀。
SEMVER = re.compile(
    r"^v?(0|[1-9][0-9]*)\.(0|[1-9][0-9]*)\.(0|[1-9][0-9]*)"
    r"(-[0-9A-Za-z-]+(\.[0-9A-Za-z-]+)*)?$"
)
BUMP_KINDS = {"major": (1, 0, 0), "minor": (0, 1, 0), "patch": (0, 0, 1)}


class VersionError(RuntimeError):
    """版本号非法或文件结构与预期不符。"""


def read_current() -> str:
    """从 backend/pyproject.toml 读取当前版本（唯一事实来源）。"""
    try:
        return str(tomllib.loads(PYPROJECT.read_text(encoding="utf-8"))["project"]["version"])
    except (OSError, KeyError, tomllib.TOMLDecodeError) as error:
        raise VersionError(f"无法读取 {PYPROJECT.relative_to(ROOT)}: {error}") from error


def resolve_target(argument: str) -> str:
    """把 major/minor/patch 或显式版本号归一成不带 v 前缀的语义版本。"""
    if argument in BUMP_KINDS:
        base = SEMVER.match(read_current())
        if base is None:
            raise VersionError(f"当前版本 {read_current()!r} 不是合法语义版本，无法自动递增")
        major, minor, patch = (int(base.group(index)) for index in (1, 2, 3))
        deltas = BUMP_KINDS[argument]
        return f"{major + deltas[0]}.{minor + deltas[1]}.{patch + deltas[2]}"

    matched = SEMVER.match(argument.strip())
    if matched is None:
        raise VersionError(
            f"版本号 {argument!r} 不合法，应为 MAJOR.MINOR.PATCH 或 "
            f"{'/'.join(sorted(BUMP_KINDS))}"
        )
    return argument.strip().lstrip("v")


def _set_toml_project_version(text: str, version: str, path: Path) -> str:
    """只改写 [project] 段的 version 行，保留其余注释与排版。"""
    lines = text.splitlines(keepends=True)
    in_project = False
    for index, line in enumerate(lines):
        stripped = line.strip()
        if stripped.startswith("["):
            in_project = stripped == "[project]"
            continue
        if in_project and re.match(r'version\s*=\s*"', stripped):
            indent = line[: len(line) - len(line.lstrip())]
            lines[index] = f'{indent}version = "{version}"\n'
            return "".join(lines)
    raise VersionError(f"{path.relative_to(ROOT)} 的 [project] 段里找不到 version 字段")


def _set_uv_lock_version(text: str, version: str) -> str:
    pattern = re.compile(
        r'(\[\[package\]\]\nname = "' + re.escape(BACKEND_PACKAGE) + r'"\nversion = )"[^"]+"'
    )
    updated, count = pattern.subn(lambda match: f'{match.group(1)}"{version}"', text)
    if count != 1:
        raise VersionError(f"{UV_LOCK.relative_to(ROOT)} 里应有且仅有一处 {BACKEND_PACKAGE} 版本，实际 {count} 处")
    return updated


def _set_package_json_version(text: str, version: str, path: Path) -> str:
    updated, count = re.subn(
        r'^(  "version": )"[^"]+"', lambda match: f'{match.group(1)}"{version}"', text, count=1, flags=re.M
    )
    if count != 1:
        raise VersionError(f"{path.relative_to(ROOT)} 顶层找不到 version 字段")
    return updated


def _set_package_lock_version(text: str, version: str) -> str:
    """package-lock.json 有两处：根对象与 packages[""]。用行扫描避免误改依赖版本。"""
    lines = text.splitlines(keepends=True)
    targets: list[int] = []

    for index, line in enumerate(lines):  # 根对象
        if re.match(r'^  "version": "[^"]+"', line):
            targets.append(index)
            break

    inside_root = False  # 是否位于 packages[""] 内
    for index, line in enumerate(lines):
        if re.match(r'^  "packages": \{', line):
            inside_root = True
            continue
        if inside_root:
            if re.match(r'^    "": \{', line):
                for offset in range(index + 1, len(lines)):
                    if re.match(r'^      "version": "[^"]+"', lines[offset]):
                        targets.append(offset)
                        break
                    if re.match(r"^    \},?$", lines[offset]):
                        break
                break
            if re.match(r"^  \},?$", line):
                break

    if len(targets) != 2:
        raise VersionError(
            f"{PACKAGE_LOCK.relative_to(ROOT)} 应有 2 处版本号（根对象与 packages[\"\"]），实际 {len(targets)} 处"
        )
    for index in targets:
        indent = lines[index][: len(lines[index]) - len(lines[index].lstrip())]
        lines[index] = f'{indent}"version": "{version}",\n'
    return "".join(lines)


def _set_openapi_version(text: str, version: str) -> str:
    """与 export_openapi 相同的序列化参数，回写后与重新生成的文件逐字节一致。"""
    document = json.loads(text)
    info = document.get("info")
    if not isinstance(info, dict) or "version" not in info:
        raise VersionError(f"{OPENAPI_JSON.relative_to(ROOT)} 缺少 info.version")
    info["version"] = version
    return json.dumps(document, ensure_ascii=False, indent=2, sort_keys=True) + "\n"


def collect_versions() -> dict[str, str]:
    """读取各文件声明的版本号，用于一致性校验。"""
    def read(path: Path) -> str:
        try:
            return path.read_text(encoding="utf-8")
        except OSError as error:
            raise VersionError(f"无法读取 {path.relative_to(ROOT)}: {error}") from error

    return {
        "backend/pyproject.toml": read_current(),
        "backend/uv.lock": _read_uv_lock_version(read(UV_LOCK)),
        "frontend/package.json": str(json.loads(read(PACKAGE_JSON))["version"]),
        "frontend/package-lock.json": str(json.loads(read(PACKAGE_LOCK))["version"]),
        "frontend/package-lock.json#packages[\"\"]": str(
            json.loads(read(PACKAGE_LOCK))["packages"][""]["version"]
        ),
        "frontend/src/api/generated/openapi.json": str(json.loads(read(OPENAPI_JSON))["info"]["version"]),
    }


def _read_uv_lock_version(text: str) -> str:
    match = re.search(
        r'\[\[package\]\]\nname = "' + re.escape(BACKEND_PACKAGE) + r'"\nversion = "([^"]+)"', text
    )
    if match is None:
        raise VersionError(f"{UV_LOCK.relative_to(ROOT)} 里找不到 {BACKEND_PACKAGE} 版本")
    return match.group(1)


def regenerate_openapi() -> None:
    """跑前端 OpenAPI 生成链路，保证产物与后端契约一致。"""
    command = "npm.cmd" if sys.platform == "win32" else "npm"
    if shutil.which(command) is None:
        raise VersionError("未找到 npm，无法重新生成 OpenAPI 产物（可用 --no-codegen 跳过）")
    result = subprocess.run(
        [command, "run", "api:generate"], cwd=ROOT / "frontend", check=False
    )
    if result.returncode != 0:
        raise VersionError(f"npm run api:generate 失败（退出码 {result.returncode}）")


def apply_version(version: str, *, dry_run: bool, codegen: bool) -> None:
    edits: list[tuple[Path, str]] = [
        (PYPROJECT, _set_toml_project_version(PYPROJECT.read_text(encoding="utf-8"), version, PYPROJECT)),
        (UV_LOCK, _set_uv_lock_version(UV_LOCK.read_text(encoding="utf-8"), version)),
        (PACKAGE_JSON, _set_package_json_version(PACKAGE_JSON.read_text(encoding="utf-8"), version, PACKAGE_JSON)),
        (PACKAGE_LOCK, _set_package_lock_version(PACKAGE_LOCK.read_text(encoding="utf-8"), version)),
    ]
    if not codegen:
        # openapi-typescript 不消费 info.version，未生成时直接回写 info 段即可保持一致。
        edits.append(
            (OPENAPI_JSON, _set_openapi_version(OPENAPI_JSON.read_text(encoding="utf-8"), version))
        )

    current = read_current()
    print(f"版本 {current} -> {version}" if current != version else f"同步版本号到 {version}")
    for path, content in edits:
        if dry_run:
            print(f"  [dry-run] {path.relative_to(ROOT)}")
            continue
        if not path.exists() or path.read_text(encoding="utf-8") != content:
            path.write_text(content, encoding="utf-8")
        print(f"  {path.relative_to(ROOT)}")

    if codegen and dry_run:
        print("  [dry-run] npm run api:generate（重新生成 OpenAPI 产物）")
    if codegen and not dry_run:
        print("重新生成 OpenAPI 产物 ...")
        regenerate_openapi()

    if dry_run:
        print("dry-run 结束，未写入任何文件")
    else:
        print("完成。建议再跑一次 `python3 scripts/bump_version.py --check` 确认一致。")


def check() -> int:
    versions = collect_versions()
    unique = set(versions.values())
    for source, value in versions.items():
        print(f"  {source:<52} {value}")
    if len(unique) != 1:
        print("版本号不一致，请运行 python3 scripts/bump_version.py <版本> 修复", file=sys.stderr)
        return 1
    print(f"版本号一致：{unique.pop()}")
    return 0


def drift() -> list[str]:
    """返回声明了非基准版本的文件列表（基准为 pyproject.toml）。"""
    versions = collect_versions()
    expected = versions["backend/pyproject.toml"]
    return [source for source, value in versions.items() if value != expected]


def main() -> int:
    parser = argparse.ArgumentParser(
        description="一键同步项目版本号", epilog="示例：python3 scripts/bump_version.py minor"
    )
    parser.add_argument(
        "version",
        nargs="?",
        help="目标版本（MAJOR.MINOR.PATCH）或 major/minor/patch 增量关键字",
    )
    parser.add_argument("--check", action="store_true", help="只校验各文件版本号是否一致")
    parser.add_argument("--dry-run", action="store_true", help="只展示将要改动的文件")
    parser.add_argument("--no-codegen", action="store_true", help="不重新生成 OpenAPI 产物")
    arguments = parser.parse_args()

    try:
        if arguments.check:
            if arguments.version:
                raise VersionError("--check 不接受版本参数")
            return check()
        if not arguments.version:
            raise VersionError("缺少版本参数（或使用 --check 校验）")
        target = resolve_target(arguments.version)
        current = read_current()
        if target == current and not drift():
            print(f"版本已经是 {target}，各文件一致，无需改动")
            return 0
        if target == current:
            print(f"版本号已是 {target}，但以下文件发生漂移，执行修复：")
            for source in drift():
                print(f"  {source}")
        apply_version(target, dry_run=arguments.dry_run, codegen=not arguments.no_codegen)
    except VersionError as error:
        print(f"错误：{error}", file=sys.stderr)
        return 2
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
