"""规则管线 HTTP 路由（Start.md §7）。

上传文书 → 提取 → 结构化为 Rule.md 草稿 → 前端审校/编辑 → 校验 → 编译为 GameDefinition。

设计：核心逻辑写成**框架无关**的纯函数（``compile_text`` / ``validate_text`` / ``ingest_text``），
便于不依赖 fastapi 单测；``build_router()`` 再把它们挂到 FastAPI 路由上（懒导入 fastapi）。
"""

from typing import Any

from app.rules import parser
from app.rules.compiler import CompileError, compile_rule_md
from app.rules.schema import RuleParseError, parse_rule_md


def validate_text(text: str) -> dict[str, Any]:
    """只解析+校验，不返回完整定义（供前端编辑器实时校验，§7.1）。"""
    try:
        spec = parse_rule_md(text)
        compile_rule_md(text)  # 编译期校验：原语/阶段引用/谓词
        return {"ok": True, "slug": spec.slug, "name": spec.name, "errors": []}
    except (RuleParseError, CompileError) as e:
        return {"ok": False, "errors": [str(e)]}


def compile_text(text: str) -> dict[str, Any]:
    """编译为 GameDefinition，返回结构摘要（角色/阶段/胜负条件）。"""
    try:
        d = compile_rule_md(text)
    except (RuleParseError, CompileError) as e:
        return {"ok": False, "errors": [str(e)]}
    return {
        "ok": True,
        "slug": d.slug,
        "name": d.name,
        "players": [d.min_players, d.max_players],
        "factions": list(d.factions),
        "roles": [{"name": r.name, "faction": r.faction, "count": r.count} for r in d.roles],
        "phases": [p.name for p in d.phases],
        "win_conditions": d.win_conditions,
    }


def ingest_text(raw_text: str, *, auto_compile: bool = True) -> dict[str, Any]:
    """完整摄取：原始文本 → 结构化为 Rule.md 草稿 →（可选）编译。

    结构化用 parser 的可注入结构器（默认启发式，无需 LLM）。草稿仍建议经人工审校再正式编译（§7.1）。
    """
    result = parser.structure_to_rule_md(raw_text)
    out: dict[str, Any] = {"rule_md_draft": result.rule_md_draft, "warnings": result.warnings}
    if auto_compile:
        out["compile"] = compile_text(result.rule_md_draft)
    return out


def build_router():
    """构造规则管线的 FastAPI 路由（懒导入 fastapi）。"""
    from fastapi import APIRouter
    from pydantic import BaseModel

    router = APIRouter(prefix="/rules", tags=["rules"])

    class TextIn(BaseModel):
        text: str

    @router.post("/validate")
    def _validate(body: TextIn) -> dict:
        return validate_text(body.text)

    @router.post("/compile")
    def _compile(body: TextIn) -> dict:
        return compile_text(body.text)

    @router.post("/ingest")
    def _ingest(body: TextIn) -> dict:
        return ingest_text(body.text)

    return router
