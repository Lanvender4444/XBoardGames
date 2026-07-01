"""嵌入向量生成（Start.md §8.2）。

记忆的写入与召回都需要把"文本/情境"映射成向量做相似度检索。真实部署可注入句向量模型
（如 bge / text-embedding-3），本模块提供一个**无外部依赖、确定性**的默认实现
``HashingEmbedder``：词袋 + 特征哈希到固定维度，使语义相近（共享词多）的文本余弦相似度更高。

设计要点：
- ``Embedder`` 是一个最小协议（``embed(text) -> list[float]``），LTM / 固化都依赖它而非具体实现，
  从而可在不改业务代码的前提下替换为真实模型（依赖注入，§4 的抽象层思路一致）。
- 默认实现确定性可复现（同样文本 → 同样向量），便于单测与对局复盘。
"""

from __future__ import annotations

import hashlib
import math
import re
from typing import Protocol, runtime_checkable

_TOKEN = re.compile(r"[\w一-鿿]+", re.UNICODE)


@runtime_checkable
class Embedder(Protocol):
    """把文本映射成定长向量。"""

    @property
    def dim(self) -> int: ...

    def embed(self, text: str) -> list[float]: ...


def tokenize(text: str) -> list[str]:
    """简单分词：英文/数字按词，中文按单字（足够支撑词袋相似度）。"""
    tokens: list[str] = []
    for m in _TOKEN.findall(text.lower()):
        if any("一" <= ch <= "鿿" for ch in m):
            tokens.extend(list(m))  # 中文逐字
        else:
            tokens.append(m)
    return tokens


class HashingEmbedder:
    """特征哈希词袋嵌入（无外部依赖，确定性）。

    每个 token 经 md5 落到 ``dim`` 个桶之一并累加权重，最后 L2 归一化。
    相似文本（共享 token 多）→ 余弦相似度高，足以驱动 top-k 召回。
    """

    def __init__(self, dim: int = 96) -> None:
        self._dim = dim

    @property
    def dim(self) -> int:
        return self._dim

    def _bucket(self, token: str) -> int:
        h = hashlib.md5(token.encode("utf-8")).digest()
        return int.from_bytes(h[:4], "big") % self._dim

    def embed(self, text: str) -> list[float]:
        vec = [0.0] * self._dim
        for tok in tokenize(text):
            vec[self._bucket(tok)] += 1.0
        norm = math.sqrt(sum(x * x for x in vec))
        if norm > 0:
            vec = [x / norm for x in vec]
        return vec


_default: Embedder | None = None


def get_embedder() -> Embedder:
    """进程级默认嵌入器。Phase 5 可换为真实句向量模型。"""
    global _default
    if _default is None:
        _default = HashingEmbedder()
    return _default
