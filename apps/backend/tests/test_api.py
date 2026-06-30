"""FastAPI 应用测试（无 fastapi 时自动跳过）。"""
from pathlib import Path

import pytest

fastapi = pytest.importorskip("fastapi")
from fastapi.testclient import TestClient  # noqa: E402

from app.api.app import create_app  # noqa: E402

WEREWOLF = Path(__file__).resolve().parents[3] / "games" / "werewolf" / "Rule.md"


@pytest.fixture()
def client():
    return TestClient(create_app())


def test_health(client):
    assert client.get("/health").json()["status"] == "ok"


def test_rules_compile_and_validate(client):
    text = WEREWOLF.read_text(encoding="utf-8")
    assert client.post("/rules/compile", json={"text": text}).json()["ok"] is True
    assert client.post("/rules/validate", json={"text": "garbage"}).json()["ok"] is False


def test_rules_ingest(client):
    out = client.post("/rules/ingest", json={"text": "# 火星狼人 5-9 人"}).json()
    assert out["compile"]["ok"] is True
    assert out["warnings"]


def test_create_session_returns_legal_actions(client):
    r = client.post("/sessions", json={"slug": "werewolf", "players": 8, "seed": 1}).json()
    assert "session_id" in r
    assert r["request_action"]  # 需行动席位
    assert r["request_action"][0]["legal_actions"]  # request_action 必带 legal_actions


def test_websocket_snapshot_and_request_action(client):
    r = client.post("/sessions", json={"slug": "werewolf", "players": 8, "seed": 1, "human_seats": [0]}).json()
    sid = r["session_id"]
    with client.websocket_connect(f"/ws/{sid}/0") as ws:
        first = ws.receive_json()
        assert first["type"] == "state_snapshot"
        assert first["payload"]["phase"] == "night"
        # 该席位若需行动，应收到带 legal_actions 的 request_action
        seats_to_act = [x["seat"] for x in r["request_action"]]
        if 0 in seats_to_act:
            msg = ws.receive_json()
            assert msg["type"] == "request_action"
            assert msg["payload"]["legal_actions"]
