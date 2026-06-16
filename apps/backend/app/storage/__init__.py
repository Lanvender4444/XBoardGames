"""存储抽象层（Start.md §4）。

业务代码只依赖本包暴露的接口（Repository / StateStore / EventBus / VectorStore）。
具体实现由 ``STORAGE_PROFILE`` 决定：

| 能力       | 接口         | local(LAN)              | server          |
|-----------|-------------|-------------------------|-----------------|
| 关系存储   | Repository  | SQLite(SQLAlchemy)      | MySQL(SQLAlchemy)|
| 热状态/缓存| StateStore  | 内嵌 redis-server        | 托管 Redis       |
| 广播       | EventBus    | Redis Pub/Sub(本机)     | Redis Pub/Sub(集群)|
| 向量检索   | VectorStore | FAISS/Chroma(本地文件)   | pgvector/托管    |

为保证 Phase 0/1 在最小依赖下可运行，本包内置纯内存实现（``memory.py``）作为默认 local 后端，
真实 Redis/SQLAlchemy 后端在对应 Phase 接入。
"""

from app.storage.base import EventBus, Repository, StateStore, VectorStore
from app.storage.factory import get_event_bus, get_repository, get_state_store, get_vector_store

__all__ = [
    "Repository",
    "StateStore",
    "EventBus",
    "VectorStore",
    "get_repository",
    "get_state_store",
    "get_event_bus",
    "get_vector_store",
]
