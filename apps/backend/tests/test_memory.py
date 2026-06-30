"""记忆系统测试（STM/LTM/羁绊/精彩瞬间/固化/嵌入）。"""
from app.engine.types import Event, Seat
from app.memory import (
    Belief,
    BondGraph,
    HighlightEvaluator,
    LongTermMemoryStore,
    Memory,
    ShortTermMemory,
    consolidate_session,
    get_embedder,
)
from app.storage.memory import InMemoryStateStore, InMemoryVectorStore


def _ev(seq, action, actor=None, round=1, **payload):
    return Event(seq=seq, phase="x", round=round, actor=actor, action=action, payload=payload)


def test_embedding_similarity_orders_by_overlap():
    e = get_embedder()

    def cos(a, b):
        return sum(x * y for x, y in zip(a, b))

    near = cos(e.embed("狼人 袭击 村民"), e.embed("狼人 袭击 平民"))
    far = cos(e.embed("狼人 袭击 村民"), e.embed("预言家 查验 金水"))
    assert near > far


def test_stm_roundtrip_and_clear():
    stm = ShortTermMemory(1, 0, store=InMemoryStateStore())
    stm.update_belief(Belief(seat=3, suspected_faction="werewolf", trust=-50))
    stm.adjust_trust(3, -80)  # clamp 到 -100
    assert stm.belief(3).trust == -100
    stm.note(3, "夜里很跳")
    assert "夜里很跳" in stm.belief(3).notes
    assert [b.seat for b in stm.beliefs()] == [3]
    stm.clear()
    assert stm.beliefs() == []


def test_ltm_recall_then_decay():
    ltm = LongTermMemoryStore(vector=InMemoryVectorStore())
    ltm.write(Memory(0, "episodic", "神预言命中3号狼人", 0.8, [3]))
    ltm.write(Memory(0, "semantic", "5号是平民", 0.3, [5]))
    hits = ltm.recall("谁是狼人", top_k=1, character_id=0)
    assert hits and "狼" in hits[0].content
    # 召回会强化命中项的 salience
    assert hits[0].salience > 0.8
    forgotten = ltm.decay(threshold=0.5)  # 0.3*0.9 < 0.5 → 遗忘语义那条
    assert forgotten >= 1


def test_ltm_recall_filters_by_character():
    ltm = LongTermMemoryStore(vector=InMemoryVectorStore())
    ltm.write(Memory(1, "semantic", "狼人 狼人", 0.5))
    ltm.write(Memory(2, "semantic", "狼人 狼人", 0.5))
    hits = ltm.recall("狼人", top_k=5, character_id=1)
    assert all(m.character_id == 1 for m in hits)


def test_bonds_save_and_betray():
    bg = BondGraph()
    bg.apply_outcome([
        _ev(0, "protect_submitted", actor=2, targets=[0]),
        _ev(1, "vote_submitted", actor=4, targets=[0]),
        _ev(2, "eliminate_submitted", actor=5, targets=[0]),
    ])
    assert bg.affinity(0, 2) > 0 and "救过我" in bg.tags(0, 2)
    assert bg.affinity(0, 4) < 0
    assert bg.affinity(0, 5) < 0


def test_bonds_enemy_tag_and_bias():
    bg = BondGraph()
    for i in range(5):
        bg.apply_outcome([_ev(i, "vote_submitted", actor=4, targets=[0])])
    assert bg.affinity(0, 4) <= -40 and "宿敌" in bg.tags(0, 4)
    bias = bg.to_behavior_bias(0, {4: 4, 2: 2})
    assert bias[4]["stance"] == "enemy"


def test_highlights_seer_hit_and_key_vote():
    events = [
        _ev(0, "investigate_result", actor=1, round=1, target=4, reveals="faction", value="werewolf"),
        _ev(1, "death", round=2, seat=4, cause="vote"),
        _ev(2, "game_over", round=3, faction="good"),
    ]
    hs = HighlightEvaluator().scan(1, events)
    kinds = {h.kind for h in hs}
    assert "神预言" in kinds and "关键一票" in kinds


def test_consolidation_writes_memories_and_updates_bonds():
    seats = [Seat(seat_id=i, actor_type="ai", role="Villager", faction="good") for i in range(3)]
    seats[1].role, seats[1].faction = "Werewolf", "werewolf"
    events = [
        _ev(0, "investigate_result", actor=0, target=1, reveals="faction", value="werewolf"),
        _ev(1, "death", round=2, seat=1, cause="vote"),
        _ev(2, "protect_submitted", actor=2, targets=[0]),
        _ev(3, "game_over", round=3, faction="good"),
    ]
    ltm = LongTermMemoryStore(vector=InMemoryVectorStore())
    bonds = BondGraph()
    res = consolidate_session(1, events, seats, ltm=ltm, bonds=bonds)
    assert res.semantic_written > 0
    assert res.episodic_written > 0
    assert bonds.affinity(0, 2) > 0  # 2 救了 0
