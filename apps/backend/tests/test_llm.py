"""LLM 驱动决策测试（langchain 决策链，默认离线 ChatModel）。"""
import pytest

from langchain_core.language_models.chat_models import BaseChatModel

from app.agents import LLMPolicy, get_chat_model
from app.agents.llm import LLMReasoner, LocalHeuristicChatModel, _argmax_hint
from app.engine import GameEngine
from app.engine.types import Seat
from app.rules.compiler import load_builtin


def test_local_model_is_langchain_chat_model():
    m = LocalHeuristicChatModel()
    assert isinstance(m, BaseChatModel)
    assert m._llm_type == "local-heuristic"


def test_get_chat_model_defaults_to_offline():
    assert isinstance(get_chat_model(), LocalHeuristicChatModel)


def test_argmax_hint_parses_candidate_block():
    text = "候选行动：\n[0] vote 目标#1 | 提示分 3.0\n[1] vote 目标#2 | 提示分 25.5\n[2] pass | 提示分 0.0"
    assert _argmax_hint(text) == 1


def test_chain_is_prompt_model_parser():
    r = LLMReasoner()
    # LCEL 链：ChatPromptTemplate | ChatModel | StrOutputParser
    assert type(r.chain).__name__ == "RunnableSequence"
    assert isinstance(r.model, BaseChatModel)


@pytest.mark.parametrize("seed", [0, 1, 7, 42])
def test_llm_policy_drives_full_game(seed):
    defn = load_builtin("werewolf")
    eng = GameEngine()
    seats = [Seat(seat_id=i, actor_type="ai") for i in range(8)]
    state = eng.init_session(defn, seats, seed=seed)
    pols = {s.seat_id: LLMPolicy(seed=100 + s.seat_id) for s in state.seats}
    wolf_on_mate = 0
    rounds = 0
    while not state.finished and rounds < 80:
        for seat in eng.actors_to_act(state):
            a = pols[seat.seat_id].decide(eng, state, seat)
            if a is None:
                continue
            if a.type in ("eliminate", "vote") and a.targets and \
                    state.seat(seat.seat_id).faction == "werewolf" and \
                    state.seat(a.targets[0]).faction == "werewolf":
                wolf_on_mate += 1
            assert eng._is_legal(state, a)  # 合法性双保险
            eng.apply(state, a)
        eng.advance_phase(state)
        rounds += 1
    assert state.finished
    assert wolf_on_mate == 0


def test_llm_policy_uses_langgraph_when_available():
    from app.agents import langgraph_available
    p = LLMPolicy(seed=1)
    if langgraph_available():
        assert p._app is not None
