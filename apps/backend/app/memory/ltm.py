"""长期记忆 LTM（Start.md §8.1 / §8.4，Phase 2 占位）。

作用域=跨局。分语义（对某角色的稳定印象）与情景（难忘事件）。
存关系表（long_term_memories）+ 向量库，通过 embedding 按当前情境召回 top-k。
控制膨胀：低 salience 且长期未召回的记忆会被合并或遗忘（§8.4）。
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import Optional

from app.storage import VectorStore, get_vector_store


@dataclass
class Memory:
    character_id: int
    kind: str       # semantic / episodic
    content: str
    salience: float
    related_character_ids: list[int]


class LongTermMemoryStore:
    def __init__(self, vector: Optional[VectorStore] = None):
        self._vector = vector or get_vector_store()

    def write(self, memory: Memory, embedding: list[float]) -> str:
        raise NotImplementedError("LTM 写入（关系表 + 向量库）待 Phase 2 接入")

    def recall(self, query_embedding: list[float], top_k: int = 5) -> list[Memory]:
        """以'当前情境'为 query 召回相关记忆（§8.2 召回节点）。"""
        raise NotImplementedError("LTM 向量召回待 Phase 2 接入")

    def decay(self) -> None:
        """衰减/合并低价值记忆，防止向量库无限增长（§8.4）。"""
        raise NotImplementedError("记忆衰减待 Phase 5")
