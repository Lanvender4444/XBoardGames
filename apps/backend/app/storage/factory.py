"""存储后端工厂（Start.md §4）。

按 ``STORAGE_PROFILE`` 选择实现。Phase 0/1 默认使用内存实现，保证最小依赖即可运行；
真实 Redis(StateStore/EventBus)、SQLAlchemy(Repository)、FAISS/pgvector(VectorStore)
将在 Phase 2/3 接入（见各 TODO）。
"""

from __future__ import annotations

from functools import lru_cache

from app.core.config import StorageProfile, settings
from app.storage.base import EventBus, Repository, StateStore, VectorStore
from app.storage.memory import (
    InMemoryEventBus,
    InMemoryRepository,
    InMemoryStateStore,
    InMemoryVectorStore,
)


@lru_cache(maxsize=1)
def get_state_store() -> StateStore:
    if settings.profile is StorageProfile.SERVER:
        # TODO Phase 3: return RedisStateStore(settings.redis_url)
        raise NotImplementedError("server StateStore (Redis) 待 Phase 3 接入")
    # local：当前内存实现；Phase 3 换为本机 redis-server sidecar 客户端。
    return InMemoryStateStore()


@lru_cache(maxsize=1)
def get_event_bus() -> EventBus:
    if settings.profile is StorageProfile.SERVER:
        # TODO Phase 3: return RedisEventBus(settings.redis_url)
        raise NotImplementedError("server EventBus (Redis Pub/Sub) 待 Phase 3 接入")
    return InMemoryEventBus()


@lru_cache(maxsize=1)
def get_repository() -> Repository:
    # TODO Phase 0+: return SqlAlchemyRepository(engine from settings.database_url)
    return InMemoryRepository()


@lru_cache(maxsize=1)
def get_vector_store() -> VectorStore:
    # TODO Phase 2: FAISS(local) / pgvector(server) per settings.vector_backend
    return InMemoryVectorStore()
