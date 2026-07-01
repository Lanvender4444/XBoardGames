"""人设 + 三级记忆 + 思维轨迹 + SSE 串行/流式 测试。"""
import json

import pytest

from app.agents.persona import PERSONAS, assign_personas
from app.engine import GameEngine
from app.engine.types import Seat
from app.rules.compiler import load_builtin

fastapi = pytest.importorskip("fastapi")
from fastapi.testclient import TestClient  # noqa: E402

from app.api.app import create_app  # noqa: E402


def _seats(n=8):
    return [Seat(seat_id=i, actor_type="ai") for i in range(n)]


def test_personas_unique_and_deterministic():
    a = assign_personas(7, _seats())
    b = assign_personas(7, _seats())
    assert len({p.name for p in a.values()}) == 8       # 同局不重复
    assert [p.name for p in a.values()] == [p.name for p in b.values()]  # 确定性


def test_three_tier_memory_in_thought():
    from app.agents.decision_graph import HeuristicPolicy
    from app.agents.orchestrator import drive
    eng = GameEngine()
    gs = eng.init_session(load_builtin("werewolf"), _seats(), seed=0)
    personas = assign_personas(0, gs.seats)
    pols = {s.seat_id: HeuristicPolicy(seed=s.seat_id, persona=personas[s.seat_id],
                                       session_id=1, character_id=s.seat_id) for s in gs.seats}
    drive(eng, gs, pols)
    # 找一个有决策记录的席位
    th = next((p.last_thought for p in pols.values() if p.last_thought), {})
    assert "beliefs" in th          # 短期：心证
    assert "mtm" in th              # 中期：本局态势
    assert "ltm" in th              # 长期：跨局召回
    assert "scores" in th and "chosen" in th and th.get("persona")


def test_persona_flavored_speech_differs():
    from app.agents.decision_graph import HeuristicPolicy
    from app.agents.orchestrator import utterance
    eng = GameEngine()
    gs = eng.init_session(load_builtin("werewolf"), _seats(), seed=0)
    personas = assign_personas(0, gs.seats)
    texts = set()
    for s in gs.seats[:4]:
        pol = HeuristicPolicy(seed=s.seat_id, persona=personas[s.seat_id])
        texts.add(utterance(pol, eng, gs, s))
    assert len(texts) >= 3  # 不同人设发言各异（口头禅不同）


def _read_stream(client, gid):
    r = client.get(f"/games/{gid}/stream")
    return [json.loads(l[6:]) for l in r.text.splitlines() if l.startswith("data: ")]


def test_sse_stream_serial_and_streaming():
    client = TestClient(create_app())
    v = client.post("/games", json={"slug": "werewolf", "players": 8, "human_seats": [0],
                                    "seed": 11, "stream": True}).json()
    gid = v["game_id"]
    seen_types = set()
    # 走几轮：人类回合就提交首个行动(stream)，否则读流
    view = v
    for _ in range(10):
        frames = _read_stream(client, gid)
        for f in frames:
            seen_types.add(f["type"])
        view = frames[-1].get("view", {})
        if view.get("finished"):
            break
        if view.get("your_turn"):
            a = view["your_actions"][0]
            client.post(f"/games/{gid}/action",
                        json={"seat": 0, "type": a["type"], "targets": a["targets"], "stream": True})
        if {"speak_delta", "thought"} <= seen_types:
            break
    assert "thinking" in seen_types      # 串行：逐个思考
    assert "thought" in seen_types       # 思维轨迹
    assert "speak_delta" in seen_types   # 流式发言分块


def test_view_exposes_personas_and_thoughts():
    client = TestClient(create_app())
    v = client.post("/games", json={"slug": "werewolf", "players": 8, "human_seats": [0], "seed": 3}).json()
    assert len(v["personas"]) == 8
    assert all("name" in p for p in v["personas"].values())
    # 驱动后应有思维记录
    assert isinstance(v["thoughts"], dict)
