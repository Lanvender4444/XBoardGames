"""引擎契约测试（Start.md §11）：init/actors_to_act/legal_actions/apply/advance_phase/check_win。"""

import pytest

from app.engine import Action, GameEngine, Seat, Visibility
from app.engine.engine import IllegalActionError, PASS
from app.rules.compiler import load_builtin


@pytest.fixture
def werewolf_def():
    return load_builtin("werewolf")


def make_state(definition, n=8, seed=1):
    engine = GameEngine()
    seats = [Seat(seat_id=i, actor_type="ai") for i in range(n)]
    return engine, engine.init_session(definition, seats, seed=seed)


def test_init_assigns_all_roles(werewolf_def):
    engine, state = make_state(werewolf_def, n=8)
    assert len(state.seats) == 8
    assert all(s.role and s.faction for s in state.seats)
    # 角色配额：2 狼、1 预言家、1 女巫、4 平民
    roles = [s.role for s in state.seats]
    assert roles.count("Werewolf") == 2
    assert roles.count("Seer") == 1
    assert roles.count("Witch") == 1
    assert roles.count("Villager") == 4
    assert state.phase == "night"


def test_player_count_bounds(werewolf_def):
    engine = GameEngine()
    with pytest.raises(ValueError):
        engine.init_session(werewolf_def, [Seat(seat_id=i) for i in range(3)])


def test_actors_to_act_in_night(werewolf_def):
    engine, state = make_state(werewolf_def, n=8)
    actors = engine.actors_to_act(state)
    actor_roles = {s.role for s in actors}
    # 夜晚行动者只来自 狼/预言家/女巫
    assert actor_roles <= {"Werewolf", "Seer", "Witch"}
    assert all(s.role != "Villager" for s in actors)


def test_seer_investigate_is_private(werewolf_def):
    engine, state = make_state(werewolf_def, n=8)
    seer = next(s for s in state.seats if s.role == "Seer")
    legal = engine.legal_actions(state, seer)
    invest = [a for a in legal if a.type == "investigate"]
    assert invest, "预言家夜晚应能查验"
    _, events = engine.apply(state, invest[0])
    result = [e for e in events if e.action == "investigate_result"]
    assert result and result[0].visibility is Visibility.PRIVATE
    assert result[0].audience == (seer.seat_id,)


def test_illegal_action_rejected(werewolf_def):
    engine, state = make_state(werewolf_def, n=8)
    villager = next(s for s in state.seats if s.role == "Villager")
    # 平民夜晚没有合法行动 → 提交查验应非法
    with pytest.raises(IllegalActionError):
        engine.apply(state, Action(seat=villager.seat_id, type="investigate", targets=(0,)))


def test_full_night_then_vote_progresses(werewolf_def):
    engine, state = make_state(werewolf_def, n=8, seed=3)
    # 让所有夜晚行动者行动（取第一个合法行动）
    for seat in list(engine.actors_to_act(state)):
        legal = engine.legal_actions(state, seat)
        engine.apply(state, legal[0])
    alive_before = len(state.alive_seats())
    engine.advance_phase(state)  # 离开 night，结算夜晚
    assert state.phase == "day_discussion"
    # 夜晚通常有人出局（除非被救/无狼行动）
    assert len(state.alive_seats()) <= alive_before


def test_check_win_good_when_no_wolves(werewolf_def):
    engine, state = make_state(werewolf_def, n=8)
    for s in state.seats:
        if s.faction == "werewolf":
            s.alive = False
    win = engine.check_win(state)
    assert win is not None and win.faction == "good"


def test_check_win_werewolf_parity(werewolf_def):
    engine, state = make_state(werewolf_def, n=8)
    # 杀到狼数 >= 好人数
    good = [s for s in state.seats if s.faction == "good"]
    wolves = [s for s in state.seats if s.faction == "werewolf"]
    for s in good[: len(good) - len(wolves)]:
        s.alive = False
    win = engine.check_win(state)
    assert win is not None and win.faction == "werewolf"


def test_engine_does_not_import_network_or_llm():
    # 引擎应为纯逻辑：不依赖 fastapi / redis / langgraph（§11）
    import app.engine.engine as eng
    src = eng.__file__
    with open(src, encoding="utf-8") as f:
        text = f.read()
    for forbidden in ("import fastapi", "import redis", "import langgraph", "import websockets"):
        assert forbidden not in text
