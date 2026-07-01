"""纯内存存储实现。

用途：
- Phase 0/1 在无 Redis/数据库环境下也能跑通引擎与 CLI 自动对局；
- 单元测试的默认后端（确定性、无外部依赖）。

行为刻意贴近 Redis 语义（TTL、hash、pub/sub），以便后续替换为真实 Redis 时上层逻辑不变。
TTL 在此实现为惰性过期（读取时检查），单进程足够。
"""

from __future__ import annotations

import time
from typing import Any, Callable, Optional


class InMemoryStateStore:
    def __init__(self) -> None:
        self._kv: dict[str, str] = {}
        self._hash: dict[str, dict[str, str]] = {}
        self._exp: dict[str, float] = {}

    def _expired(self, key: str) -> bool:
        exp = self._exp.get(key)
        if exp is not None and time.monotonic() > exp:
            self._kv.pop(key, None)
            self._hash.pop(key, None)
            self._exp.pop(key, None)
            return True
        return False

    def get(self, key: str) -> Optional[str]:
        if self._expired(key):
            return None
        return self._kv.get(key)

    def set(self, key: str, value: str, ttl: Optional[int] = None) -> None:
        self._kv[key] = value
        if ttl is not None:
            self._exp[key] = time.monotonic() + ttl

    def delete(self, key: str) -> None:
        self._kv.pop(key, None)
        self._hash.pop(key, None)
        self._exp.pop(key, None)

    def hset(self, key: str, field: str, value: str) -> None:
        self._hash.setdefault(key, {})[field] = value

    def hgetall(self, key: str) -> dict[str, str]:
        if self._expired(key):
            return {}
        return dict(self._hash.get(key, {}))

    def expire(self, key: str, ttl: int) -> None:
        self._exp[key] = time.monotonic() + ttl


class InMemoryEventBus:
    def __init__(self) -> None:
        self._subs: dict[str, list[Callable[[str], None]]] = {}

    def publish(self, channel: str, message: str) -> None:
        for handler in list(self._subs.get(channel, [])):
            handler(message)

    def subscribe(self, channel: str, handler: Callable[[str], None]) -> None:
        self._subs.setdefault(channel, []).append(handler)

    def unsubscribe(self, channel: str) -> None:
        self._subs.pop(channel, None)


class InMemoryRepository:
    """极简内存仓储（按 model 类型分桶）。真实实现见 server/sqlalchemy 后端。"""

    def __init__(self) -> None:
        self._store: dict[type, list[Any]] = {}

    def add(self, entity: Any) -> Any:
        self._store.setdefault(type(entity), []).append(entity)
        return entity

    def get(self, model: type, pk: Any) -> Optional[Any]:
        for e in self._store.get(model, []):
            if getattr(e, "id", None) == pk:
                return e
        return None

    def list(self, model: type, **filters: Any) -> list[Any]:
        items = self._store.get(model, [])
        if not filters:
            return list(items)
        return [e for e in items if all(getattr(e, k, None) == v for k, v in filters.items())]

    def commit(self) -> None:  # 内存实现无事务
        pass


class InMemoryVectorStore:
    def __init__(self) -> None:
        self._vecs: dict[str, tuple[list[float], dict[str, Any]]] = {}

    @staticmethod
    def _cosine(a: list[float], b: list[float]) -> float:
        import math

        if not a or not b or len(a) != len(b):
            return 0.0
        dot = sum(x * y for x, y in zip(a, b))
        na = math.sqrt(sum(x * x for x in a))
        nb = math.sqrt(sum(y * y for y in b))
        return dot / (na * nb) if na and nb else 0.0

    def upsert(self, vid: str, vector: list[float], metadata: dict[str, Any]) -> None:
        self._vecs[vid] = (vector, metadata)

    def query(self, vector: list[float], top_k: int = 5) -> list[tuple[str, float, dict]]:
        scored = [
            (vid, self._cosine(vector, vec), meta) for vid, (vec, meta) in self._vecs.items()
        ]
        scored.sort(key=lambda t: t[1], reverse=True)
        return scored[:top_k]

    def delete(self, vid: str) -> None:
        self._vecs.pop(vid, None)
