"""文书 → 结构化抽取（Start.md §7.1 ①②，Phase 4 占位）。

管线：文书(PDF/docx/txt/图片) → ①提取(OCR/文本) → ②LLM 结构化 → Rule.md（草稿）→
③人工审校（前端编辑器）→ ④编译（见 compiler.py）。

本模块当前为接口占位：定义签名与数据流，真实实现接入 OCR 与 LLM（Phase 4）。
"""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path


@dataclass
class ExtractResult:
    text: str
    rule_md_draft: str  # ②的产物：Rule.md 草稿，待人工审校
    warnings: list[str]


def extract_text(document_path: Path) -> str:
    """①提取：从 PDF/docx/txt/图片抽取纯文本（OCR 兜底）。"""
    raise NotImplementedError("文书文本提取待 Phase 4 接入（pdf/docx 解析 + OCR）")


def structure_to_rule_md(raw_text: str) -> ExtractResult:
    """②结构化：用 LLM 从原始文本抽取角色/阶段/动作/胜负条件，产出 Rule.md 草稿。

    抽取会有歧义和遗漏——所以草稿必须经第③步人工审校才允许编译（§7.1）。
    """
    raise NotImplementedError("LLM 规则结构化待 Phase 4 接入")
