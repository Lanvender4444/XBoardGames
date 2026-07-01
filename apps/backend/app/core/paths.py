"""统一的可写路径解析（Start.md §1 / §4 / §15）。

所有可写数据（SQLite、Redis dump、上传文书、向量库文件）必须落到平台用户可写目录，
**绝不**写进安装目录——避免打包后（Tauri + PyInstaller sidecar）的写权限问题
（`sys._MEIPASS` 只读）。

本模块是可写路径的单一出口。其它模块一律通过这里取目录，不要自己拼路径。
"""

from __future__ import annotations

import os
import sys
from pathlib import Path

APP_DIR_NAME = "ai-tabletop"


def _is_frozen() -> bool:
    """是否运行在 PyInstaller 打包产物中（sidecar 模式）。"""
    return getattr(sys, "frozen", False) and hasattr(sys, "_MEIPASS")


def user_data_dir() -> Path:
    """平台相关的用户可写数据根目录。

    - Windows: %APPDATA%\\ai-tabletop
    - macOS:   ~/Library/Application Support/ai-tabletop
    - Linux:   $XDG_DATA_HOME/ai-tabletop 或 ~/.local/share/ai-tabletop

    可用环境变量 ``AI_TABLETOP_DATA_DIR`` 覆盖（测试/服务器部署用）。
    """
    override = os.environ.get("AI_TABLETOP_DATA_DIR")
    if override:
        base = Path(override)
    elif sys.platform.startswith("win"):
        base = Path(os.environ.get("APPDATA", Path.home() / "AppData" / "Roaming")) / APP_DIR_NAME
    elif sys.platform == "darwin":
        base = Path.home() / "Library" / "Application Support" / APP_DIR_NAME
    else:
        xdg = os.environ.get("XDG_DATA_HOME")
        base = (Path(xdg) if xdg else Path.home() / ".local" / "share") / APP_DIR_NAME
    base.mkdir(parents=True, exist_ok=True)
    return base


def _sub(name: str) -> Path:
    p = user_data_dir() / name
    p.mkdir(parents=True, exist_ok=True)
    return p


def db_path() -> Path:
    """LAN(local) profile 的 SQLite 文件路径。"""
    return _sub("db") / "ai-tabletop.sqlite"


def redis_dump_dir() -> Path:
    """内嵌 redis-server 的 dump.rdb 落盘目录（LAN sidecar）。"""
    return _sub("redis")


def uploads_dir() -> Path:
    """上传的规则源文书存放目录（Start.md §5 rule_documents.storage_path）。"""
    return _sub("uploads")


def vector_dir() -> Path:
    """本地向量库（FAISS/Chroma）文件目录（Start.md §4 / §8）。"""
    return _sub("vector")


def logs_dir() -> Path:
    return _sub("logs")


def resource_dir() -> Path:
    """只读资源目录（打包内置 Rule.md 等）。打包态指向 _MEIPASS，开发态指向仓库 games/。"""
    if _is_frozen():
        return Path(sys._MEIPASS)  # type: ignore[attr-defined]
    # 开发态：apps/backend/app/core/paths.py -> 仓库根
    return Path(__file__).resolve().parents[4]
