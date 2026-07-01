"""规则摄取管线测试：front-matter 透传、骨架兜底、完整 ingest 编译。"""
from pathlib import Path

from app.rules import ingest, structure_to_rule_md
from app.rules.compiler import compile_rule_md

WEREWOLF = Path(__file__).resolve().parents[3] / "games" / "werewolf" / "Rule.md"


def test_passthrough_existing_rule_md():
    text = WEREWOLF.read_text(encoding="utf-8")
    res = structure_to_rule_md(text)
    assert res.warnings == []
    assert res.rule_md_draft.lstrip().startswith("---")
    compile_rule_md(res.rule_md_draft)  # 透传草稿可编译


def test_skeleton_for_free_text_has_warnings_and_compiles():
    res = structure_to_rule_md("# 火星狼人  一个 5-9 人 的社交推理游戏")
    assert res.warnings  # 提示需人工审校
    d = compile_rule_md(res.rule_md_draft)
    assert d.min_players == 5 and d.max_players == 9


def test_ingest_pipeline_compiles_draft():
    out = ingest(text=WEREWOLF.read_text(encoding="utf-8"))
    assert out["compiled"]["ok"] is True


def test_extract_text_reads_md(tmp_path):
    from app.rules.parser import extract_text
    p = tmp_path / "r.md"
    p.write_text("# hello", encoding="utf-8")
    assert "hello" in extract_text(p)
