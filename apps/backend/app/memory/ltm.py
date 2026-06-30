"""长期记忆 LTM（Start.md §8.1 / §8.4）。

作用域=跨局。分语义（对某角色的稳定印象）与情景（难忘事件）。
通过 embedding 按"当前情境"向量召回 top-k；低 salience 且久未召回的记忆会被衰减/遗忘（§8.4）。

实现说明：
- 记忆内容与元数据写入 ``VectorStore``（默认内存实现，余弦检索），同时本对象维护 id 索引以支持衰减遍历。
- 真实部署把 ``VectorStore`` 换成 FAISS/pgvector、把内容主存换成 ``long_term_memories`` 关系表即可，
  本类的方法签名与语义不变（§4 抽象层）。
- 召回会就地强化 ``salience`` 并把 age 归零，实现"常被想起的记忆更牢固"。
"""
from __future__ import annotations

import itertools
from dataclasses import dataclass, field
from typing import Optional

from app.memory.embedding import Embedder, get_embedder
from app.storage import VectorStore, get_vector_store

_ids = itertools.count(1)


@dataclass
class Memory:
    character_id: int
    kind: str  # semantic / episodic
    content: str
    salience: float
    related_character_ids: list[int] = field(default_factory=list)
    vid: Optional[str] = None
    age: int = 0  # 自写入以来经历的 decay 轮数（久未召回则增长）


class LongTermMemoryStore:
    def __init__(
        self, vector: Optional[VectorStore] = None, embedder: Optional[Embedder] = None
    ) -> None:
        self._vector = vector or get_vector_store()
        self._embedder = embedder or get_embedder()
        self._index: dict[str, Memory] = {}  # id -> Memory（衰减遍历用；真实部署为关系表）

    # write
    def write(self, memory: Memory, embedding: Optional[list[float]] = None) -> str:
        """写入一条记忆：存向量库 + 索引，返回记忆 id。embedding 缺省由内容自动生成。"""
        vid = memory.vid or f"m{next(_ids)}"
        memory.vid = vid
        vec = embedding if embedding is not None else self._embedder.embed(memory.content)
        meta = {
            "character_id": memory.character_id,
            "kind": memory.kind,
            "content": memory.content,
            "salience": memory.salience,
            "related": list(memory.related_character_ids),
        }
        self._vector.upsert(vid, vec, meta)
        self._index[vid] = memory
        return vid

    # recall
    def recall(
        self,
        query: "str | list[float]",
        top_k: int = 5,
        character_id: Optional[int] = None,
    ) -> list[Memory]:
        """以'当前情境'召回相关记忆（§8.2 召回节点）。

        query 可为文本（自动嵌入）或现成向量；character_id 给定时只召回属于该角色的记忆。
        命中记忆会被小幅强化（salience += 0.1，age 归零）。
        """
        qvec = self._embedder.embed(query) if isinstance(query, str) else query
        hits = self._vector.query(qvec, top_k=top_k * 3 if character_id is not None else top_k)
        out: list[Memory] = []
        for vid, _score, _meta in hits:
            mem = self._index.get(vid)
            if mem is None:
                continue
            if character_id is not None and mem.character_id != character_id:
                continue
            mem.salience = min(1.0, mem.salience + 0.1)
            mem.age = 0
            out.append(mem)
            if len(out) >= top_k:
                break
        return out

    # decay
    def decay(self, threshold: float = 0.15, rate: float = 0.1, max_age: int = 5) -> int:
        """衰减/遗忘低价值记忆（§8.4，Phase 5）。

        每条记忆 age+1、salience 按 rate 衰减；当 salience < threshold 或 age > max_age 时遗忘
        （从向量库与索引删除）。返回被遗忘的条数，防止向量库无限膨胀。
        """
        forgotten = 0
        for vid in list(self._index):
            mem = self._index[vid]
            mem.age += 1
            mem.salience = round(mem.salience * (1 - rate), 4)
            if mem.salience < threshold or mem.age > max_age:
                self._vector.delete(vid)
                del self._index[vid]
                forgotten += 1
        return forgotten

    def all(self, character_id: Optional[int] = None) -> list[Memory]:
        mems = list(self._index.values())
        if character_id is not None:
            mems = [m for m in mems if m.character_id == character_id]
        return mems
