"""编排器测试：阶段模式、并发抢占、排队发言、LangGraph 全 AI 整局。"""
import pytest

from app.agents import langgraph_available
from app.agents.decision_graph import HeuristicPolicy
from app.agents.orchestrator import (
    PREEMPTIVE,
    QUEUED,
    drive,
    phase_mode,
    run_orchestrator,
    step_queued,
    utterance,
)
from app.engine import GameEngine
from app.engine.types import Seat
from app.rules.compiler import load_builtin


def _game(seed=0, n=8):
    defn = load_builtin("werewolf")
    eng = GameEngine()
    seats = [Seat(seat_id=i, actor_type="ai") for i in range(n)]
    gs = eng.init_session(defn, seats, seed=seed)
    pols = {s.seat_id: HeuristicPolicy(seed=seed + s.seat_id) for s in seats}
    return eng, gs, pols


def test_phase_mode_mapping():
    eng, gs, _ = _game(1)
    assert phase_mode(gs) == PREEMPTIVE  # night
    # 推进到讨论阶段
    while gs.phase != "day_discussion" and not gs.finished:
        for s in eng.actors_to_act(gs):
            eng.apply(gs, eng.legal_actions(gs, s)[0])
        eng.advance_phase(gs)
    if not gs.finished:
        assert phase_mode(gs) == QUEUED  # day_discussion


def test_drive_full_ai_finishes_with_speeches():
    eng, gs, pols = _game(2)
    drive(eng, gs, pols)
    assert gs.finished
    assert any(e.action == "speak" and e.payload.get("text") for e in gs.log)


def test_queued_speeches_in_seat_order():
    eng, gs, pols = _game(3)
    # 跳到讨论阶段
    while phase_mode(gs) != QUEUED and not gs.finished:
        for s in eng.actors_to_act(gs):
            eng.apply(gs, eng.legal_actions(gs, s)[0])
        eng.advance_phase(gs)
    if gs.finished:
        return
    before = len(gs.log)
    step_queued(eng, gs, pols)
    speakers = [e.actor for e in gs.log[before:] if e.action == "speak"]
    assert speakers == sorted(speakers)  # 按座位序轮流发言


def test_drive_stops_for_human():
    eng, gs, pols = _game(5)
    # 人类是 0 号；若 0 号当前需行动，drive 应在其回合前停下
    drive(eng, gs, {k: v for k, v in pols.items() if k != 0}, human_seats=(0,))
    actors = [s.seat_id for s in eng.actors_to_act(gs)]
    assert gs.finished or 0 in actors  # 要么结束，要么停在人类回合


@pytest.mark.skipif(not langgraph_available(), reason="需要 langgraph")
@pytest.mark.parametrize("seed", [0, 1, 42])
def test_langgraph_orchestrator_runs(seed):
    eng, gs, pols = _game(seed)
    run_orchestrator(eng, gs, pols, max_steps=400)
    assert gs.finished and gs.winner.faction in ("good", "werewolf")


def test_utterance_returns_text():
    eng, gs, pols = _game(7)
    seat = gs.seats[0]
    txt = utterance(pols[0], eng, gs, seat)
    assert isinstance(txt, str) and len(txt) > 0
