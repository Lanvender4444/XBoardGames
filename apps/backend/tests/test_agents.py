"""AI 决策子图测试：启发式策略跑通整局、狼不刀队友、预言家利用查验结果。"""
import pytest

from app.agents import AIPlayer, HeuristicPolicy, RandomPolicy
from app.agents.decision_graph import DecisionGraph, GraphContext
from app.engine import GameEngine
from app.engine.engine import PASS
from app.engine.types import Seat
from app.rules.compiler import load_builtin


def _play(policy_factory, seed):
    defn = load_builtin("werewolf")
    eng = GameEngine()
    seats = [Seat(seat_id=i, actor_type="ai") for i in range(8)]
    state = eng.init_session(defn, seats, seed=seed)
    pols = {s.seat_id: policy_factory(s.seat_id) for s in state.seats}
    wolf_on_mate = 0
    rounds = 0
    while not state.finished and rounds < 80:
        for seat in eng.actors_to_act(state):
            a = pols[seat.seat_id].decide(eng, state, seat)
            if a is None:
                continue
            if a.type in ("eliminate", "vote") and a.targets:
                if state.seat(seat.seat_id).faction == "werewolf" and \
                        state.seat(a.targets[0]).faction == "werewolf":
                    wolf_on_mate += 1
            eng.apply(state, a)
        eng.advance_phase(state)
        rounds += 1
    return state, wolf_on_mate


@pytest.mark.parametrize("seed", [0, 1, 7, 42, 123])
def test_heuristic_game_converges(seed):
    state, _ = _play(lambda sid: HeuristicPolicy(seed=100 + sid), seed)
    assert state.finished
    assert state.winner.faction in ("good", "werewolf")


@pytest.mark.parametrize("seed", [0, 1, 7, 42, 123])
def test_heuristic_wolves_never_target_teammates(seed):
    _, wolf_on_mate = _play(lambda sid: HeuristicPolicy(seed=100 + sid), seed)
    assert wolf_on_mate == 0


def test_random_policy_still_works():
    state, _ = _play(lambda sid: RandomPolicy(seed=sid), 3)
    assert state.finished


def test_seer_uses_investigation_to_distrust_wolf():
    # 预言家查到狼后，子图召回会把对该席位的信任打到很低
    defn = load_builtin("werewolf")
    eng = GameEngine()
    seats = [Seat(seat_id=i, actor_type="ai") for i in range(8)]
    state = eng.init_session(defn, seats, seed=11)
    seer = next(s for s in state.seats if s.role == "Seer")
    wolf = next(s for s in state.seats if s.faction == "werewolf")
    pol = HeuristicPolicy(seed=1)
    # 预言家先查验那个狼
    from app.engine.types import Action
    eng.apply(state, Action(seat=seer.seat_id, type="investigate", targets=(wolf.seat_id,)))
    # 让子图 recall 跑一遍（通过 decide）
    pol.decide(eng, state, seer)
    assert pol.beliefs[wolf.seat_id].suspected_faction == "werewolf"
    assert pol.beliefs[wolf.seat_id].trust < 0


def test_ai_player_defaults_to_llm():
    from app.agents import LLMPolicy
    p = AIPlayer(character_id=1)
    assert isinstance(p.policy, LLMPolicy)  # AI 角色默认由 LLM 决策链操控
