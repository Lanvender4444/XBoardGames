"""记忆系统（Start.md §8，Phase 2 占位）。

- STM 短期记忆：单局，Redis，带 TTL（心证/信任度）。
- LTM 长期记忆：跨局，关系表 + 向量库，按情境召回。
- 羁绊 Bonds：角色间有向关系数值 + 标签，直接影响 AI 行为。
- 精彩瞬间 + 局结束固化（consolidation）。
"""

from app.memory.bonds import BondGraph
from app.memory.consolidation import consolidate_session
from app.memory.highlights import HighlightEvaluator
from app.memory.ltm import LongTermMemoryStore
from app.memory.stm import ShortTermMemory

__all__ = [
    "ShortTermMemory",
    "LongTermMemoryStore",
    "BondGraph",
    "HighlightEvaluator",
    "consolidate_session",
]
