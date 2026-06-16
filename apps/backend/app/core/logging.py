"""轻量日志配置。落盘到用户可写目录（Start.md §4）。"""

from __future__ import annotations

import logging
from logging.handlers import RotatingFileHandler

from app.core import paths

_CONFIGURED = False


def get_logger(name: str) -> logging.Logger:
    global _CONFIGURED
    if not _CONFIGURED:
        root = logging.getLogger("app")
        root.setLevel(logging.INFO)
        fmt = logging.Formatter("%(asctime)s %(levelname)s %(name)s: %(message)s")

        stream = logging.StreamHandler()
        stream.setFormatter(fmt)
        root.addHandler(stream)

        try:
            fh = RotatingFileHandler(
                paths.logs_dir() / "backend.log", maxBytes=2_000_000, backupCount=3
            )
            fh.setFormatter(fmt)
            root.addHandler(fh)
        except OSError:
            pass  # 文件日志不可用时退化为仅控制台
        _CONFIGURED = True
    return logging.getLogger(name if name.startswith("app") else f"app.{name}")
