import json
import os
import tempfile
from pathlib import Path
from typing import Any


def fsync_directory(path: Path) -> None:
    """同步目录元数据，确保文件创建、替换或删除操作耐久落盘。"""
    if os.name == "nt":
        return
    flags = os.O_RDONLY | getattr(os, "O_DIRECTORY", 0)
    descriptor = os.open(path, flags)
    try:
        os.fsync(descriptor)
    finally:
        os.close(descriptor)


def durable_replace(source: Path, destination: Path) -> None:
    """同步源文件后原子替换目标，并同步目标目录。"""
    destination.parent.mkdir(parents=True, exist_ok=True)
    with source.open("rb") as source_file:
        os.fsync(source_file.fileno())
    os.replace(source, destination)
    fsync_directory(destination.parent)


def durable_unlink(path: Path) -> bool:
    """删除文件并同步父目录；文件不存在时返回 False。"""
    try:
        path.unlink()
    except FileNotFoundError:
        return False
    fsync_directory(path.parent)
    return True


def atomic_write_text(path: Path, content: str) -> None:
    """通过同目录临时文件原子替换目标文件。"""
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary_path: Path | None = None
    try:
        with tempfile.NamedTemporaryFile(
            mode="w",
            encoding="utf-8",
            dir=path.parent,
            prefix=f".{path.name}.",
            suffix=".tmp",
            delete=False,
        ) as temporary_file:
            temporary_file.write(content)
            temporary_file.flush()
            temporary_path = Path(temporary_file.name)
        durable_replace(temporary_path, path)
    finally:
        if temporary_path is not None:
            temporary_path.unlink(missing_ok=True)


def atomic_write_json(path: Path, payload: Any, *, indent: int = 2) -> None:
    """以 UTF-8 JSON 格式原子写入目标文件。"""
    atomic_write_text(path, json.dumps(payload, ensure_ascii=False, indent=indent))
