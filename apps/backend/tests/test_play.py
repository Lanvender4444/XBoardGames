"""可玩对局 API + LLM 配置测试（人类 + AI，离线模型）。"""
from pathlib import Path

import pytest

fastapi = pytest.importorskip("fastapi")
from fastapi.testclient import TestClient  # noqa: E402

from app.agents import providers  # noqa: E402
from app.api.app import create_app  # noqa: E402
from app.api.play import PlayService  # noqa: E402


@pytest.fixture()
def client():
    return TestClient(create_app())


def test_providers_cover_mainstream(client):
    ids = {p["id"] for p in client.get("/providers").json()["providers"]}
    for expect in {"openai", "deepseek", "moonshot", "zhipu", "qwen", "openrouter",
                   "groq", "ollama", "anthropic", "offline", "custom"}:
        assert expect in ids


def test_llm_config_roundtrip_masks_key(client):
    out = client.post("/llm/config", json={"provider": "deepseek", "api_key": "sk-secret123", "model": "deepseek-chat"}).json()
    assert out["provider"] == "deepseek" and out["has_key"] is True
    assert "secret" not in out["api_key"]  # 脱敏
    client.post("/llm/config", json={"provider": "offline"})  # 复位


def test_create_and_play_full_game(client):
    v = client.post("/games", json={"slug": "werewolf", "players": 8, "human_seats": [0], "seed": 1}).json()
    gid = v["game_id"]
    assert v["your_role"] is not None  # 自己的身份可见
    steps = 0
    while not v["finished"] and steps < 300:
        steps += 1
        if v["your_turn"]:
            a = v["your_actions"][0]
            v = client.post(f"/games/{gid}/action",
                            json={"seat": v["your_seat"], "type": a["type"], "targets": a["targets"]}).json()
        else:
            break
    assert v["finished"]
    assert v["winner"] in ("good", "werewolf")


def test_view_hides_other_roles_until_finished():
    svc = PlayService()
    gid = svc.create_game("werewolf", 8, [0], seed=2)
    view = svc.view(gid, 0)
    others = [s for s in view["seats"] if s["seat"] != 0 and view["finished"] is False]
    if not view["finished"]:
        assert all(s["role"] is None for s in others)


def test_illegal_action_returns_400(client):
    v = client.post("/games", json={"slug": "werewolf", "players": 8, "human_seats": [0], "seed": 3}).json()
    gid = v["game_id"]
    r = client.post(f"/games/{gid}/action", json={"seat": 0, "type": "investigate", "targets": [999]})
    assert r.status_code == 400


def test_provider_factory_offline_default():
    providers.set_runtime_config({"provider": "offline"})
    from app.agents.llm import LocalHeuristicChatModel
    assert isinstance(providers.build_chat_model(), LocalHeuristicChatModel)


def _to_discussion(eng, gs):
    while gs.phase != "day_discussion" and not gs.finished:
        for s in eng.actors_to_act(gs):
            eng.apply(gs, eng.legal_actions(gs, s)[0])
        eng.advance_phase(gs)
    return gs


def test_human_speak_text_persists():
    from app.engine import GameEngine
    from app.engine.types import Action, Seat
    from app.rules.compiler import load_builtin

    eng = GameEngine()
    gs = eng.init_session(load_builtin("werewolf"),
                          [Seat(seat_id=i, actor_type="ai") for i in range(8)], seed=0)
    _to_discussion(eng, gs)
    if gs.finished:
        return
    sp = gs.alive_seats()[0]
    eng.apply(gs, Action(seat=sp.seat_id, type="speak", channel="public",
                         extra={"text": "我是好人，别怀疑我"}))
    assert any(e.action == "speak" and e.actor == sp.seat_id
               and e.payload.get("text") == "我是好人，别怀疑我" for e in gs.log)


def test_night_kill_tiebreak_not_always_seat0():
    """狼群平票不再固定刀最小席位（否则人类#0 每晚被刀，不可玩）。"""
    from app.agents.decision_graph import HeuristicPolicy
    from app.agents.orchestrator import drive
    from app.engine import GameEngine
    from app.engine.types import Seat
    from app.rules.compiler import load_builtin

    eng = GameEngine()
    seat0_deaths = 0
    for seed in range(20):
        gs = eng.init_session(load_builtin("werewolf"),
                              [Seat(seat_id=i, actor_type="ai") for i in range(8)], seed=seed)
        pols = {s.seat_id: HeuristicPolicy(seed=seed + s.seat_id) for s in gs.seats}
        drive(eng, gs, pols, max_steps=2)  # 跑到首个夜晚结算
        n1 = [e for e in gs.log if e.action == "death" and e.round == 1 and e.payload.get("cause") == "eliminate"]
        if any(e.payload.get("seat") == 0 for e in n1):
            seat0_deaths += 1
    assert seat0_deaths < 20  # 不再是 100% 刀 0 号
