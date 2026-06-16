"""规则摄取管线（Start.md §7）：文书 → Rule.md → Game Definition。

四步：①提取(OCR/文本) ②结构化(LLM 抽取) ③人工审校 ④编译。
本包提供：
- ``primitives``  能力原语库（编译器只认这有限的一组）
- ``schema``      Rule.md 规范与解析/校验
- ``compiler``    Rule.md → GameDefinition（状态机 + 原语绑定）
- ``parser``      文书 → 结构化抽取（LLM，Phase 4 占位）
"""

from app.rules.compiler import CompileError, compile_rule_md, load_builtin
from app.rules.schema import RuleSpec, parse_rule_md

__all__ = [
    "primitives",
    "RuleSpec",
    "parse_rule_md",
    "compile_rule_md",
    "load_builtin",
    "CompileError",
]
