"""记忆系统（Start.md §8）。

- STM 短期记忆：单局，StateStore(Redis 语义)，带 TTL（心证/信任度）。
- LTM 长期记忆：跨局，向量库召回（+ 关系表主存可选），salience 衰减防膨胀。
- 羁绊 Bonds：角色间有向关系数值 + 标签，直接影响 AI 行为偏置。
- 精彩瞬间 Highlights + 局结束固化 consolidation。
- 嵌入 embedding：默认无依赖哈希嵌入，可注入真实句向量模型。
"""

from app.memory.bonds import Bond, BondGraph
from app.memory.consolidation import ConsolidationResult, consolidate_session
from app.memory.embedding import Embedder, HashingEmbedder, get_embedder
from app.memory.highlights import Highlight, HighlightEvaluator
from app.memory.ltm import LongTermMemoryStore, Memory
from app.memory.mtm import MediumTermMemory
from app.memory.stm import Belief, ShortTermMemory

__all__ = [
    "ShortTermMemory",
    "Belief",
    "MediumTermMemory",
    "LongTermMemoryStore",
    "Memory",
    "BondGraph",
    "Bond",
    "HighlightEvaluator",
    "Highlight",
    "consolidate_session",
    "ConsolidationResult",
    "Embedder",
    "HashingEmbedder",
    "get_embedder",
]
