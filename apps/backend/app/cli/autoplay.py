"""命令行自动对局（Start.md §14 Phase 1 里程碑）。

用"随机合法行动"策略驱动全 AI 的一整局，逐回合打印事件，直到满足胜负条件。
这是验证引擎抽象是否成立的关键工具：引擎不区分行动来源，CLI 与未来的人类 WebSocket、
AI LangGraph 走的是同一条 ``apply`` 路径（§11）。

用法：
    uv run python -m app.cli.autoplay --game werewolf --players 8 --seed 42
    uv run python -m app.cli.autoplay --game werewolf --players 8 --seed 42 --quiet
"""

from __future__ import annotations

import argparse
import sys
from typing import Optional

from app.agents.decision_graph import RandomPolicy
from app.engine import Action, Event, GameEngine, GameState, Seat, Visibility
from app.engine.engine import PASS
from app.rules.compiler import load_builtin


def run_game(
    slug: str,
    players: int,
    seed: int = 0,
    max_rounds: int = 50,
    on_event: Optional[callable] = None,
) -> GameState:
    """跑通一整局，返回终局状态。``on_event`` 可选地接收每条新事件用于打印。"""
    definition = load_builtin(slug)
    engine = GameEngine()
    # 全 AI 局；actor_type 不影响引擎逻辑，只标注来源
    seats = [Seat(seat_id=i, actor_type="ai") for i in range(players)]
    state = engine.init_session(definition, seats, seed=seed)
    policy = RandomPolicy(seed=seed)

    _flush(state, 0, on_event)
    safety = 0
    while not state.finished and state.round <= max_rounds:
        safety += 1
        if safety > max_rounds * 20:
            raise RuntimeError("对局未收敛（疑似规则/引擎死循环）")
        before = len(state.log)
        # 收集当前阶段所有待行动席位的行动
        for seat in engine.actors_to_act(state):
            action = policy.decide(engine, state, seat)
            if action is None:
                action = Action(seat=seat.seat_id, type=PASS)
            engine.apply(state, action)
        # 阶段结算 + 转移
        engine.advance_phase(state)
        _flush(state, before, on_event)
    return state


def _flush(state: GameState, since: int, on_event: Optional[callable]) -> None:
    if on_event is None:
        return
    for ev in state.log[since:]:
        on_event(state, ev)


def _seat_label(state: GameState, seat_id: Optional[int]) -> str:
    if seat_id is None:
        return "—"
    s = state.seat(seat_id)
    return f"#{seat_id}({s.role})"


def _print_event(state: GameState, ev: Event) -> None:
    actor = _seat_label(state, ev.actor)
    vis = "" if ev.visibility is Visibility.PUBLIC else f" [{ev.visibility.value}]"
    print(f"  [r{ev.round}/{ev.phase}] {actor} {ev.action} {ev.payload}{vis}")


def main(argv: Optional[list[str]] = None) -> int:
    parser = argparse.ArgumentParser(description="AI Tabletop 引擎自动对局")
    parser.add_argument("--game", default="werewolf", help="内置游戏 slug（werewolf）")
    parser.add_argument("--players", type=int, default=8)
    parser.add_argument("--seed", type=int, default=0)
    parser.add_argument("--quiet", action="store_true", help="只打印结果，不逐条打印事件")
    args = parser.parse_args(argv)

    print(f"== {args.game} | players={args.players} | seed={args.seed} ==")
    state = run_game(
        args.game,
        args.players,
        seed=args.seed,
        on_event=None if args.quiet else _print_event,
    )

    print("-- 角色公开 --")
    for s in state.seats:
        status = "存活" if s.alive else "出局"
        print(f"  #{s.seat_id} {s.name}: {s.role}/{s.faction} ({status})")
    if state.winner:
        print(f"== 胜者阵营: {state.winner.faction}  （条件: {state.winner.reason}）==")
    else:
        print("== 未分胜负（达到最大回合）==")
    return 0


if __name__ == "__main__":
    sys.exit(main())
