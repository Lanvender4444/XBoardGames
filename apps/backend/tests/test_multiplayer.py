"""联机层测试：会话生命周期、广播、断线 AI 托管、房间发现。"""
import pytest

from app.agents import HeuristicPolicy
from app.engine import GameEngine
from app.engine.engine import IllegalActionError
from app.engine.types import Action, Seat
from app.multiplayer import SessionManager, announce_room, discover_rooms, withdraw_room
from app.multiplayer.discovery import clear_rooms
from app.rules.compiler import load_builtin
from app.storage.memory import InMemoryEventBus, InMemoryStateStore


def _mgr():
    return SessionManager(state_store=InMemoryStateStore(), event_bus=InMemoryEventBus())


def _new_session(sm, human=(0,)):
    defn = load_builtin("werewolf")
    seats = [Seat(seat_id=i, actor_type=("human" if i in human else "ai")) for i in range(8)]
    return sm.create_session(defn, seats, seed=3)


def test_create_and_request_action():
    sm = _mgr()
    sid = _new_session(sm)
    reqs = sm.request_action(sid)
    assert reqs and all("legal_actions" in r and r["legal_actions"] for r in reqs)


def test_submit_broadcasts_events():
    sm = _mgr()
    captured = []
    sid = _new_session(sm)
    sm._bus.subscribe(f"channel:session:{sid}", lambda m: captured.append(m))
    seat = sm.request_action(sid)[0]["seat"]
    legal = sm.request_action(sid)[0]["legal_actions"][0]
    sm.submit_action(sid, legal)
    assert len(captured) >= 1


def test_illegal_action_raises():
    sm = _mgr()
    sid = _new_session(sm)
    with pytest.raises(IllegalActionError):
        sm.submit_action(sid, Action(seat=0, type="investigate", targets=(999,)))


def test_disconnect_ai_takeover_and_reconnect():
    sm = _mgr()
    sid = _new_session(sm, human=(0,))
    sm.on_disconnect(sid, 0)
    assert sm.state(sid).seat(0).actor_type == "ai"
    assert sm.is_offline(sid, 0)
    snap = sm.on_reconnect(sid, 0)
    assert not sm.is_offline(sid, 0)
    assert snap["seats"][0]["seat"] == 0


def test_drive_ai_finishes_game():
    sm = _mgr()
    sid = _new_session(sm, human=())
    pols = {s.seat_id: HeuristicPolicy(seed=s.seat_id) for s in sm.state(sid).seats}
    sm.drive_ai(sid, pols)
    assert sm.state(sid).finished


def test_snapshot_hides_other_roles():
    sm = _mgr()
    sid = _new_session(sm)
    snap = sm.snapshot(sid, for_seat=0)
    mine = [s for s in snap["seats"] if s["seat"] == 0][0]
    others = [s for s in snap["seats"] if s["seat"] != 0]
    assert mine["role"] is not None
    assert all(o["role"] is None for o in others)  # 未结束时不泄露他人身份


def test_room_discovery():
    clear_rooms()
    announce_room("s1", "127.0.0.1", 8765, "客厅")
    assert any(r["session_id"] == "s1" for r in discover_rooms())
    withdraw_room("s1")
    assert not any(r["session_id"] == "s1" for r in discover_rooms())
