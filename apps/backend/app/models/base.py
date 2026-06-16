"""SQLAlchemy 声明基类与通用列。

SQLite ↔ MySQL 的差异（类型、并发）收敛在迁移脚本里（Alembic）；模型代码两端不变（§4）。
JSON 列用 SQLAlchemy 的可移植 ``JSON`` 类型，两端均支持。
"""

from __future__ import annotations

from datetime import datetime

from sqlalchemy import DateTime, func
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column


class Base(DeclarativeBase):
    pass


class TimestampMixin:
    created_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(
        DateTime, server_default=func.now(), onupdate=func.now()
    )
