"""精彩瞬间评估器（Start.md §8.3，Phase 5 占位）。

扫描 session_events，识别高戏剧性事件（神预言命中、最后一票翻盘、成功深度欺骗、关键自爆等），
用 LLM 生成标题与摘要，存 highlight_moments 并关联事件区间（可回放）。
涉及人类玩家的瞬间会沉淀为 AI 对**这位玩家**的长期记忆（"记得你上次那波操作"）。
"""
from __future__ import annotations

from dataclasses import dataclass


@dataclass
class Highlight:
    title: str
    summary: str
    kind: str            # 神预言/极限翻盘/经典欺骗...
    participants: list[int]
    replay_ref: str


class HighlightEvaluator:
    def scan(self, session_id: int, events: list) -> list[Highlight]:
        raise NotImplementedError("瞬间评估待 Phase 5 接入")
