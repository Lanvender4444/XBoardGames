"""游戏引擎实现（Start.md §11）。

契约方法：
    init_session / actors_to_act / legal_actions / apply / advance_phase / check_win

实现要点：
- 服务器权威：引擎是状态唯一权威，``apply`` 先做合法性校验再改状态（§9.1）。
- 行动来源无关：人类与 AI 行动都是 ``Action``，走同一条 ``apply`` 路径（§11）。
- 结算按阶段的 ``resolution_order``（§7.2）。夜晚行动累积后在离开夜晚时统一结算；
  投票累积后在 ``on_complete`` 结算。
- 可见性：查验等私有结果只对行动者可见（``Visibility.PRIVATE``）。

引擎对原语的语义做最小内置实现（eliminate/protect/investigate/vote/speak/nominate...），
足以驱动狼人杀与阿瓦隆；新机制通过扩展原语库实现，而非在规则里塞任意逻辑（§7.3）。
"""

from __future__ import annotations

import random
from collections import Counter
from typing import Optional

from app.engine import predicates
from app.engine.types import (
    Action,
    AbilityDef,
    Event,
    GameDefinition,
    GameState,
    PhaseDef,
    Seat,
    Visibility,
    WinResult,
)

PASS = "pass"


class IllegalActionError(ValueError):
    """提交了不在 ``legal_actions`` 中的行动（防作弊 / 防 AI 幻觉，§9.1 / §10）。"""


class GameEngine:
    # ------------------------------------------------------------------ init
    def init_session(
        self,
        definition: GameDefinition,
        players: list[Seat],
        seed: Optional[int] = None,
    ) -> GameState:
        """初始化状态机：按角色配额分配身份，写入能力次数，进入起始阶段。"""
        n = len(players)
        if not (definition.min_players <= n <= definition.max_players):
            raise ValueError(
                f"{definition.name} 需要 {definition.min_players}-{definition.max_players} 人，得到 {n}"
            )

        roles = self._expand_roles(definition, n)
        rng = random.Random(seed)
        rng.shuffle(roles)

        seats: list[Seat] = []
        for i, p in enumerate(players):
            role_name = roles[i]
            role = definition.role(role_name)
            seats.append(
                Seat(
                    seat_id=i,
                    actor_type=p.actor_type,
                    role=role_name,
                    faction=role.faction,
                    alive=True,
                    name=p.name or f"P{i}",
                )
            )

        state = GameState(
            definition=definition,
            seats=seats,
            phase=definition.start_phase,
            round=1,
        )
        # 初始化能力剩余次数
        for s in seats:
            for ab in definition.role(s.role).abilities:
                if ab.uses is not None:
                    state.ability_uses[(s.seat_id, ab.primitive)] = ab.uses
        self._emit(state, None, "game_start", {"players": n}, Visibility.PUBLIC)
        self._emit(state, None, "phase_enter", {"phase": state.phase}, Visibility.PUBLIC)
        return state

    def _expand_roles(self, definition: GameDefinition, n: int) -> list[str]:
        roles: list[str] = []
        rest_role: Optional[str] = None
        for r in definition.roles:
            if r.count == "rest":
                rest_role = r.name
            else:
                roles.extend([r.name] * int(r.count))
        if rest_role is not None:
            roles.extend([rest_role] * (n - len(roles)))
        if len(roles) != n:
            raise ValueError(
                f"角色配额({len(roles)})与玩家数({n})不符；检查 Rule.md 的 count 设置"
            )
        return roles

    # -------------------------------------------------------------- scheduling
    def actors_to_act(self, state: GameState) -> list[Seat]:
        """当前阶段仍需行动、且尚未提交的席位。"""
        if state.finished:
            return []
        phase = state.definition.phase(state.phase)
        result: list[Seat] = []
        for s in self._phase_seats(state, phase):
            if s.seat_id in state.acted:
                continue
            if self.legal_actions(state, s):
                result.append(s)
        return result

    def _phase_seats(self, state: GameState, phase: PhaseDef) -> list[Seat]:
        if phase.actors in ("all_alive", "all"):
            return [s for s in state.alive_seats()]
        return [s for s in state.alive_seats() if s.role in phase.actor_roles]

    # ------------------------------------------------------------ legal actions
    def legal_actions(self, state: GameState, seat: Seat) -> list[Action]:
        if state.finished or not seat.alive:
            return []
        phase = state.definition.phase(state.phase)
        actions: list[Action] = []

        # 阶段级通用行动（不绑定角色能力）：vote / speak / nominate
        if "vote" in phase.actions:
            actions += self._vote_options(state, seat)
        if "speak" in phase.actions:
            actions.append(Action(seat=seat.seat_id, type="speak", channel="public"))
        if "nominate" in phase.actions:
            actions += self._nominate_options(state, seat, phase)

        # 角色能力行动（夜晚私有行动等）
        role = state.definition.role(seat.role)
        optional = False
        for ab in role.abilities:
            if ab.phase and ab.phase != state.phase:
                continue
            if ab.uses is not None and state.ability_uses.get((seat.seat_id, ab.primitive), 0) <= 0:
                continue
            opts = self._ability_options(state, seat, ab)
            if opts:
                actions += opts
                optional = optional or ab.uses is not None  # 有限次能力视为可选

        # 可选能力允许“跳过”
        if optional or (not actions and seat.role in phase.actor_roles):
            actions.append(Action(seat=seat.seat_id, type=PASS))
        return actions

    def _targets_other_alive(self, state: GameState, seat: Seat) -> list[int]:
        return [s.seat_id for s in state.alive_seats() if s.seat_id != seat.seat_id]

    def _vote_options(self, state: GameState, seat: Seat) -> list[Action]:
        opts = [
            Action(seat=seat.seat_id, type="vote", targets=(t,))
            for t in self._targets_other_alive(state, seat)
        ]
        opts.append(Action(seat=seat.seat_id, type="vote", targets=(), extra={"abstain": True}))
        return opts

    def _nominate_options(self, state: GameState, seat: Seat, phase: PhaseDef) -> list[Action]:
        # 占位：阿瓦隆队长组队。Phase 4 接入完整 nominate 语义。
        return []

    def _ability_options(self, state: GameState, seat: Seat, ab: AbilityDef) -> list[Action]:
        prim = ab.primitive
        if prim in ("eliminate", "protect", "investigate"):
            target_spec = ab.params.get("target", "single_other")
            if target_spec == "single_other":
                return [
                    Action(seat=seat.seat_id, type=prim, targets=(t,))
                    for t in self._targets_other_alive(state, seat)
                ]
            if target_spec == "single_any":
                return [
                    Action(seat=seat.seat_id, type=prim, targets=(t,))
                    for t in (s.seat_id for s in state.alive_seats())
                ]
        if prim == "speak":
            return [Action(seat=seat.seat_id, type="speak", channel=ab.params.get("channel"))]
        return []

    # -------------------------------------------------------------------- apply
    def apply(self, state: GameState, action: Action) -> tuple[GameState, list[Event]]:
        """校验 + 收集/即时结算 + 产出事件。"""
        if state.finished:
            raise IllegalActionError("游戏已结束")
        if not self._is_legal(state, action):
            raise IllegalActionError(
                f"非法行动: seat={action.seat} type={action.type} targets={action.targets}"
            )

        start = len(state.log)
        seat = state.seat(action.seat)
        state.acted.add(action.seat)

        if action.type == PASS:
            self._emit(state, action.seat, "pass", {}, Visibility.PRIVATE, audience=(action.seat,))
            return state, state.log[start:]

        if action.type == "speak":
            self._emit(
                state,
                action.seat,
                "speak",
                {"channel": action.channel, "text": action.extra.get("text", "")},
                Visibility.FACTION if action.channel and action.channel != "public" else Visibility.PUBLIC,
            )
            return state, state.log[start:]

        if action.type == "investigate":
            # 即时私有揭示（§7.2 reveals: faction/role）
            ab = self._ability(state, seat, "investigate")
            target = state.seat(action.targets[0])
            reveals = (ab.params.get("reveals") if ab else None) or "faction"
            value = target.faction if reveals == "faction" else target.role
            self._consume_use(state, seat, "investigate")
            self._emit(
                state,
                action.seat,
                "investigate_result",
                {"target": target.seat_id, "reveals": reveals, "value": value},
                Visibility.PRIVATE,
                audience=(action.seat,),
            )
            return state, state.log[start:]

        # 其余（eliminate/protect/vote/nominate）累积，待阶段结算
        state.pending.setdefault(action.type, []).append(action)
        if action.type in ("eliminate", "protect"):
            self._consume_use(state, seat, action.type)
        # 夜晚私有行动只对本人可见；公开投票对所有人可见。
        is_vote = action.type == "vote"
        payload = {"targets": list(action.targets)}
        if action.extra.get("abstain"):
            payload["abstain"] = True
        self._emit(
            state,
            action.seat,
            f"{action.type}_submitted",
            payload,
            Visibility.PUBLIC if is_vote else Visibility.PRIVATE,
            audience=() if is_vote else (action.seat,),
        )
        return state, state.log[start:]

    def _is_legal(self, state: GameState, action: Action) -> bool:
        legal = self.legal_actions(state, state.seat(action.seat))
        for la in legal:
            if la.type == action.type and tuple(la.targets) == tuple(action.targets):
                return True
        return False

    def _ability(self, state: GameState, seat: Seat, primitive: str) -> Optional[AbilityDef]:
        for ab in state.definition.role(seat.role).abilities:
            if ab.primitive == primitive:
                return ab
        return None

    def _consume_use(self, state: GameState, seat: Seat, primitive: str) -> None:
        key = (seat.seat_id, primitive)
        if key in state.ability_uses:
            state.ability_uses[key] = max(0, state.ability_uses[key] - 1)

    # ----------------------------------------------------------- advance phase
    def advance_phase(self, state: GameState) -> tuple[GameState, list[Event]]:
        """结算本阶段累积行动，按 next 转移，必要时检查胜负。"""
        if state.finished:
            return state, []
        start = len(state.log)
        phase = state.definition.phase(state.phase)

        # 1) 结算
        if phase.resolution_order:
            self._resolve_night(state, phase)
        if phase.on_complete == "eliminate_top_voted":
            self._resolve_vote(state, phase)

        # 2) 胜负检查（阶段标了 check_win，或刚发生死亡）
        if phase.check_win or phase.resolution_order:
            win = self.check_win(state)
            if win:
                state.finished = True
                state.winner = win
                self._emit(state, None, "game_over", {"faction": win.faction, "reason": win.reason})
                return state, state.log[start:]

        # 3) 阶段转移
        nxt = phase.next
        state.acted.clear()
        state.pending.clear()
        if nxt is None:
            return state, state.log[start:]
        # 回到起始阶段视为进入新一轮
        if nxt == state.definition.start_phase:
            state.round += 1
        state.phase = nxt
        self._emit(state, None, "phase_enter", {"phase": nxt, "round": state.round})
        return state, state.log[start:]

    def _resolve_night(self, state: GameState, phase: PhaseDef) -> None:
        protected: set[int] = set()
        for prim in phase.resolution_order:
            if prim == "protect":
                for act in state.pending.get("protect", []):
                    if act.targets:
                        protected.add(act.targets[0])
            elif prim == "eliminate":
                victims = self._eliminate_victims(state)
                for victim in sorted(victims):
                    if victim not in protected and state.seat(victim).alive:
                        state.seat(victim).alive = False
                        self._emit(state, None, "death", {"seat": victim, "cause": "eliminate"})
            # investigate 已在 apply 即时结算

    def _eliminate_victims(self, state: GameState) -> set[int]:
        """区分群体决策击杀（狼队，多人指向取多数）与个体击杀（女巫毒等，各自生效）。"""
        group_targets: list[int] = []
        solo_targets: list[int] = []
        for act in state.pending.get("eliminate", []):
            if not act.targets:
                continue
            ab = self._ability(state, state.seat(act.seat), "eliminate")
            if ab and ab.params.get("group_decision"):
                group_targets.append(act.targets[0])
            else:
                solo_targets.append(act.targets[0])
        victims: set[int] = set(solo_targets)
        if group_targets:
            tally = Counter(group_targets)
            top = max(tally.values())
            victims.add(sorted(t for t, c in tally.items() if c == top)[0])
        return victims

    def _resolve_vote(self, state: GameState, phase: PhaseDef) -> None:
        votes = state.pending.get("vote", [])
        tally: Counter[int] = Counter()
        for a in votes:
            if a.extra.get("abstain") or not a.targets:
                continue
            tally[a.targets[0]] += 1
        self._emit(state, None, "vote_result", {"tally": dict(tally)})
        if not tally:
            return
        top = max(tally.values())
        leaders = sorted(t for t, c in tally.items() if c == top)
        # 平票规则：占位为“无人出局”（tie_rule=no_elim）；可由 Rule.md 配置覆盖
        if len(leaders) > 1:
            self._emit(state, None, "vote_tie", {"candidates": leaders})
            return
        victim = leaders[0]
        if state.seat(victim).alive:
            state.seat(victim).alive = False
            self._emit(state, None, "death", {"seat": victim, "cause": "vote"})

    # ---------------------------------------------------------------- check win
    def check_win(self, state: GameState) -> Optional[WinResult]:
        ctx = self._win_context(state)
        for faction, predicate in state.definition.win_conditions.items():
            if predicates.evaluate(predicate, ctx):
                return WinResult(faction=faction, reason=predicate)
        return None

    def _win_context(self, state: GameState) -> dict[str, int]:
        ctx: dict[str, int] = {"alive_count": len(state.alive_seats())}
        for f in state.definition.factions:
            ctx[f"{f}_count"] = state.faction_count(f, alive_only=True)
        return ctx

    # -------------------------------------------------------------------- utils
    def _emit(
        self,
        state: GameState,
        actor: Optional[int],
        action: str,
        payload: dict,
        visibility: Visibility = Visibility.PUBLIC,
        audience: tuple[int, ...] = (),
    ) -> Event:
        ev = Event(
            seq=state.seq,
            phase=state.phase,
            round=state.round,
            actor=actor,
            action=action,
            payload=payload,
            visibility=visibility,
            audience=audience,
        )
        state.seq += 1
        state.log.append(ev)
        return ev
