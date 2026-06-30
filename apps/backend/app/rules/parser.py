"""文书 → 结构化抽取（Start.md §7.1 ①②）。

完整管线：文书(PDF/docx/txt/md) → ①提取(文本/OCR) → ②结构化为 Rule.md 草稿 →
③人工审校（前端编辑器）→ ④编译（见 compiler.py）。

结构化(②)的"理解任意自然语言规则书"在生产里由 LLM 承担。本模块把这一步抽象成可注入的
``Structurer`` 协议，并提供一个**无外部依赖、确定性**的默认实现 ``HeuristicStructurer``：
- 若输入已是带 YAML front-matter 的 Rule.md → 直接透传（已结构化）。
- 若输入是受支持的轻量 `key: value` 迷你格式 → 抽取为 Rule.md。
- 否则 → 产出最小骨架草稿 + 警告，提示需人工补全（仍走第③步审校）。
真实 LLM 结构器实现同一协议即可插入，处理任意散文规则书；下游编译/审校不变。
"""
from __future__ import annotations

import re
from dataclasses import dataclass, field
from pathlib import Path
from typing import Optional, Protocol


@dataclass
class ExtractResult:
    text: str
    rule_md_draft: str  # ②的产物：Rule.md 草稿，待人工审校
    warnings: list = field(default_factory=list)


# --------------------------------------------------------------------------- #
# ① 提取
# --------------------------------------------------------------------------- #
def extract_text(document_path: Path) -> str:
    """从 PDF/docx/txt/md 抽取纯文本。

    txt/md 直接读；pdf/docx 尝试可选库（pypdf / python-docx），未安装则抛出明确提示。
    """
    document_path = Path(document_path)
    suffix = document_path.suffix.lower()
    if suffix in (".txt", ".md", ""):
        return document_path.read_text(encoding="utf-8")
    if suffix == ".pdf":
        try:
            from pypdf import PdfReader
        except ImportError as e:
            raise ImportError("解析 PDF 需 `pip install pypdf`") from e
        reader = PdfReader(str(document_path))
        return "\n".join(page.extract_text() or "" for page in reader.pages)
    if suffix in (".docx",):
        try:
            import docx  # python-docx
        except ImportError as e:
            raise ImportError("解析 docx 需 `pip install python-docx`") from e
        d = docx.Document(str(document_path))
        return "\n".join(p.text for p in d.paragraphs)
    raise ValueError(f"暂不支持的文书类型: {suffix}")


# --------------------------------------------------------------------------- #
# ② 结构化
# --------------------------------------------------------------------------- #
class Structurer(Protocol):
    def structure(self, raw_text: str) -> ExtractResult: ...


def _has_frontmatter(text: str) -> bool:
    t = text.lstrip()
    return t.startswith("---") and len(t.split("---", 2)) >= 3


_SKELETON = """---
slug: {slug}
name: {name}
min_players: {minp}
max_players: {maxp}
start_phase: night
factions: [good, werewolf]
win_conditions:
  good: "werewolf_count == 0"
  werewolf: "werewolf_count >= good_count"
roles:
  - name: Werewolf
    faction: werewolf
    count: {wolves}
    abilities:
      - eliminate: {{ target: single_other, phase: night, group_decision: true }}
  - name: Villager
    faction: good
    count: rest
phases:
  - name: night
    actors: "Werewolf"
    resolution_order: [eliminate]
    next: day_vote
  - name: day_vote
    actors: all_alive
    actions: [vote]
    on_complete: eliminate_top_voted
    next: night
    check_win: true
---

# {name}

> 自动生成的骨架草稿，需人工审校补全角色与阶段（§7.1 第③步）。
"""


class HeuristicStructurer:
    """确定性结构化：front-matter 透传 / 关键字抽取 / 骨架兜底。"""

    def structure(self, raw_text: str) -> ExtractResult:
        # (a) 已是 Rule.md → 透传
        if _has_frontmatter(raw_text):
            return ExtractResult(text=raw_text, rule_md_draft=raw_text.lstrip(), warnings=[])

        warnings: list = []
        # 抽取标题
        m = re.search(r"^#\s*(.+)$", raw_text, re.MULTILINE)
        name = (m.group(1).strip() if m else "未命名游戏")
        slug_m = re.search(r"slug[:：]\s*([a-z0-9_-]+)", raw_text, re.IGNORECASE)
        slug = slug_m.group(1) if slug_m else "custom_game"
        # 抽取人数 "6-12 人" / "6到12人" / "players: 6-12"
        pm = re.search(r"(\d+)\s*[-到~]\s*(\d+)\s*(?:人|players)?", raw_text)
        minp, maxp = (int(pm.group(1)), int(pm.group(2))) if pm else (6, 12)
        # 狼人数：默认按人数 1/4 取整
        wolves = max(1, (minp) // 4)

        warnings.append("未检测到结构化 front-matter；已生成骨架草稿，请人工审校补全角色/阶段/胜负条件。")
        draft = _SKELETON.format(slug=slug, name=name, minp=minp, maxp=maxp, wolves=wolves)
        return ExtractResult(text=raw_text, rule_md_draft=draft, warnings=warnings)


_default_structurer: Optional[Structurer] = None


def get_structurer() -> Structurer:
    """进程级默认结构器。Phase 4 可替换为真实 LLM 结构器（实现同一协议）。"""
    global _default_structurer
    if _default_structurer is None:
        _default_structurer = HeuristicStructurer()
    return _default_structurer


def structure_to_rule_md(raw_text: str, structurer: Optional[Structurer] = None) -> ExtractResult:
    """②结构化：从原始文本抽取角色/阶段/动作/胜负条件，产出 Rule.md 草稿。

    抽取会有歧义和遗漏——所以草稿必须经第③步人工审校才允许正式编译（§7.1）。
    """
    return (structurer or get_structurer()).structure(raw_text)


# --------------------------------------------------------------------------- #
# 完整管线
# --------------------------------------------------------------------------- #
def ingest(
    document_path: Optional[Path] = None,
    *,
    text: Optional[str] = None,
    structurer: Optional[Structurer] = None,
    compile_draft: bool = True,
) -> dict:
    """端到端摄取：提取 → 结构化 →（可选）编译。返回草稿/警告/编译结果。

    第③步人工审校在前端编辑器进行，不在此自动化；compile_draft=True 仅用于"草稿是否已可编译"的即时反馈。
    """
    raw = text if text is not None else extract_text(Path(document_path))  # type: ignore[arg-type]
    res = structure_to_rule_md(raw, structurer)
    out: dict = {"rule_md_draft": res.rule_md_draft, "warnings": list(res.warnings)}
    if compile_draft:
        from app.rules.compiler import CompileError, compile_rule_md
        from app.rules.schema import RuleParseError

        try:
            d = compile_rule_md(res.rule_md_draft)
            out["compiled"] = {"ok": True, "slug": d.slug, "phases": [p.name for p in d.phases]}
        except (RuleParseError, CompileError) as e:
            out["compiled"] = {"ok": False, "errors": [str(e)]}
    return out
