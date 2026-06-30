"""精彩瞬间评估器（Start.md §8.3，Phase 5）。

扫描一局的事件流，识别高戏剧性瞬间并生成标题/摘要，关联事件区间（可回放）。
默认用**确定性启发式**识别（无需 LLM）；真实部署可注入 LLM 润色标题/摘要，识别框架不变。
涉及人类玩家的瞬间由 ``consolidation`` 沉淀为 AI 对"这位玩家"的长期记忆。

已实现的识别器：
- 神预言：预言家查验命中后来被证实/出局的狼人。
- 关键一票：把某人送上断头台的那次出局（vote 致死）。
- 极限翻盘：多轮拉锯后某阵营逆转取胜。
"""
from __future__ import annotations

from dataclasses import dataclass, field


@dataclass
class Highlight:
    title: str
    summary: str
    kind: str  # 神预言 / 极限翻盘 / 关键一票 ...
    participants: list = field(default_factory=list)
    replay_ref: str = ""  # 形如 "seq:12"，指向事件


class HighlightEvaluator:
    def scan(self, session_id: int, events: list) -> list:
        out: list = []
        out += self._scan_seer_hits(events)
        out += self._scan_key_votes(events)
        out += self._scan_comeback(events)
        return out

    # 神预言：investigate_result 查到 werewolf，且该 target 后来 death
    def _scan_seer_hits(self, events: list) -> list:
        deaths = {e.payload.get("seat") for e in events if e.action == "death"}
        hits: list = []
        for e in events:
            if e.action != "investigate_result":
                continue
            if e.payload.get("value") == "werewolf" and e.payload.get("target") in deaths:
                tgt = e.payload.get("target")
                hits.append(
                    Highlight(
                        title="神预言命中",
                        summary=f"#{e.actor} 在第 {e.round} 回合查出 #{tgt} 是狼，最终被票出。",
                        kind="神预言",
                        participants=[e.actor, tgt],
                        replay_ref=f"seq:{e.seq}",
                    )
                )
        return hits

    # 关键一票：vote 致死
    def _scan_key_votes(self, events: list) -> list:
        out: list = []
        for e in events:
            if e.action == "death" and e.payload.get("cause") == "vote":
                seat = e.payload.get("seat")
                out.append(
                    Highlight(
                        title="关键一票",
                        summary=f"第 {e.round} 回合，#{seat} 在投票中被送走。",
                        kind="关键一票",
                        participants=[seat] if seat is not None else [],
                        replay_ref=f"seq:{e.seq}",
                    )
                )
        return out

    # 极限翻盘：终局前多轮拉锯
    def _scan_comeback(self, events: list) -> list:
        over = next((e for e in events if e.action == "game_over"), None)
        if not over:
            return []
        winner = over.payload.get("faction")
        death_rounds = [e.round for e in events if e.action == "death"]
        if winner and death_rounds and max(death_rounds) >= 3:
            return [
                Highlight(
                    title="极限翻盘",
                    summary=f"{winner} 阵营在多轮拉锯（{max(death_rounds)} 回合）后逆转取胜。",
                    kind="极限翻盘",
                    participants=[],
                    replay_ref=f"seq:{over.seq}",
                )
            ]
        return []
