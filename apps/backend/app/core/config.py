"""运行时配置（Start.md §4 存储分层）。

通过环境变量 ``STORAGE_PROFILE`` 在 LAN(local) 与 server 之间切换；业务代码只依赖接口。
保持零三方依赖（不引入 pydantic-settings），让核心在 ``uv sync`` 最小依赖下即可导入。
"""

from __future__ import annotations

import os
from dataclasses import dataclass
from enum import Enum

from app.core import paths


class StorageProfile(str, Enum):
    LOCAL = "local"  # LAN：SQLite + 内嵌 redis-server sidecar + 本地向量文件
    SERVER = "server"  # 部署：MySQL + 托管 Redis + pgvector/托管向量库


@dataclass(frozen=True)
class Settings:
    profile: StorageProfile
    database_url: str
    redis_url: str
    vector_backend: str  # faiss | chroma | pgvector

    @property
    def is_local(self) -> bool:
        return self.profile is StorageProfile.LOCAL


def _default_database_url(profile: StorageProfile) -> str:
    if profile is StorageProfile.LOCAL:
        return f"sqlite:///{paths.db_path()}"
    # server：默认占位，部署时由环境变量提供真实凭证
    return os.environ.get(
        "DATABASE_URL", "mysql+pymysql://user:pass@localhost:3306/ai_tabletop"
    )


def load_settings() -> Settings:
    profile = StorageProfile(os.environ.get("STORAGE_PROFILE", "local"))
    database_url = os.environ.get("DATABASE_URL") or _default_database_url(profile)
    redis_url = os.environ.get("REDIS_URL", "redis://127.0.0.1:6379/0")
    vector_backend = os.environ.get(
        "VECTOR_BACKEND", "faiss" if profile is StorageProfile.LOCAL else "pgvector"
    )
    return Settings(
        profile=profile,
        database_url=database_url,
        redis_url=redis_url,
        vector_backend=vector_backend,
    )


# 进程级单例（按需读取一次）
settings = load_settings()
