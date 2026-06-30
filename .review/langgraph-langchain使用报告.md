# LangChain / LangGraph 使用情况报告

> ⚠️ 更新：本报告是"实现 LangGraph 版决策子图**之前**"的盘点。现已新增基于 LangGraph `StateGraph`
> 的真实实现（`app/agents/langgraph_graph.py` + `LangGraphPolicy`），langgraph 不再只是预留——
> 详见 [`langgraph决策子图实现报告.md`](langgraph决策子图实现报告.md)。下文保留为"接入前"历史快照。

> 目的：盘点本项目里所有涉及 langchain / langgraph 的地方，说明各自是"真用了"还是"预留/设计"，
> 以及当前实际怎么用、将来怎么接。

## TL;DR（结论先行）

**目前代码里没有任何一行真正 `import langgraph` 或 `import langchain`。** 全仓库对二者的引用只有四类：

1. **可选依赖声明**（`pyproject.toml` 的 `ai` extra）——声明了但默认不安装、不导入。
2. **设计意图**（`docs/Start.md §10`）——规划中的 AI 编排框架。
3. **预留接缝 + 参考实现**（`app/agents/decision_graph.py`）——决策子图当前用**纯 Python** 实现，
   结构刻意对齐 LangGraph，注释标明"可在 langgraph 上重建同构子图"。
4. **架构守护**（`docs` 注释 + 引擎纯净性单测）——强调引擎**不依赖** langgraph，并有测试断言禁止其被引擎导入。

一句话：**LangGraph 是"规划的 AI 编排层"，当前以等价的纯 Python 决策子图落地，留好了插入口；
langchain-core 仅在未来接 LLM 时随 `ai` extra 引入。两者现在都不是运行时依赖。**

---

## 1. 出现位置清单

| 位置 | 类别 | 说明 |
|---|---|---|
| `apps/backend/pyproject.toml` `ai` extra | 可选依赖 | `langgraph>=0.2`、`langchain-core>=0.3`；标注 "Phase 2 AI 玩家 + 记忆"。**默认 `uv sync` 不装**，需显式 `uv sync --extra ai`。 |
| `apps/backend/app/agents/decision_graph.py` | 预留接缝 + 参考实现 | 决策子图用纯 Python 实现；docstring/注释两处提到"注入 LLM 推理节点"、"可在 langgraph 上重建同构子图；本编排器即其参考实现"。 |
| `apps/backend/app/engine/__init__.py`、`app/cli/autoplay.py` | 注释 | 说明"AI 行动从 LangGraph 进来，与人类行动一样变成 `Action` 喂给 `apply`"——表达解耦原则，非真实调用。 |
| `apps/backend/tests/test_engine.py` | 架构守护测试 | `test_engine_does_not_import_network_or_llm`：断言引擎源码不含 `import langgraph`（等）。**主动确保引擎不依赖它**。 |
| `apps/backend/README.md`、`docs/Start.md §10/§11`、`.review/*` | 文档 | 设计与说明。 |

> 验证命令：`grep -rnE "^\s*(import|from)\s+(langgraph|langchain)" apps/backend` → **无匹配**（零真实导入）。

---

## 2. 设计意图：为什么选 LangGraph（Start.md §10）

把游戏建模成"带状态的图"正是 LangGraph 的强项，规划分两层：

- **外层 · 游戏编排图**：节点=阶段（night/day_vote…），边=阶段转移（由 Rule.md 编译而来），
  状态=完整牌局。每个阶段节点收集该阶段所有 actor 的行动。
- **内层 · AI 玩家决策子图**（每个需行动的 AI 角色调用一次）：
  `感知 → 召回 → 推理 → 行动 → 编码`，其中**推理节点用 LLM 结合人物卡 persona/traits 产出决策**。

三个要点：人物卡驱动差异（persona 注入 prompt）、合法性双保险（LLM 产出仍过引擎校验）、
成本控制（召回 top-k、低风险阶段用小模型）。

---

## 3. 当前怎么落地的（用纯 Python 等价实现）

`app/agents/decision_graph.py` 把上面的**内层决策子图**用纯 Python 实现了出来，**结构与 LangGraph 一一对应**：

```
DecisionGraph.run(ctx):
    perceive(ctx)   ① 感知：取 engine.legal_actions、识别狼队友
    recall(ctx)     ② 召回：扫"自己可见的"私有事件→STM 心证；取 BondGraph 行为偏置
    reason(ctx)     ③ 推理：Reasoner.score() 给每个合法行动打分      ← LLM 将插在这里
    act(ctx)        ④ 行动：取最高分 → engine._is_legal 合法性双保险
    encode(ctx)     ⑤ 编码：心证写回（跨回合记忆）
```

- **推理节点是接缝**：抽象成 `Reasoner` 协议（`score(ctx, action)->float`）。
  当前默认实现是 `HeuristicReasoner`（无需 LLM、确定性的启发式打分：狼不刀队友、预言家查未知、投最可疑）。
- **外层游戏编排图**：当前由 `SessionManager` / `cli.autoplay` 的"收集 actors_to_act → apply → advance_phase"
  循环承担——等价于外层图的节点推进，只是没用 langgraph 的图执行器。

为什么这样做：沙箱/最小依赖下无法装/跑 LLM 与 langgraph，纯 Python 等价实现能让整条 AI 决策链**真实可运行、可单测、可复盘**（20 局启发式对局全收敛、狼零次误伤队友）。

---

## 4. 将来怎么真正接 LangGraph + LangChain

不改引擎、不改业务流程，只需两步：

1. **装依赖**：`uv sync --extra ai`（引入 `langgraph` + `langchain-core`）。
2. **实现并注入一个基于 LLM 的 `Reasoner`**（或用 langgraph 重建 perceive→…→encode 子图）：
   - 在推理节点里，用 `recall` 召回的 LTM 记忆 + `BondGraph` 行为偏置 + 人物卡 persona/traits 拼 prompt，
     调用 LLM（经 langchain-core 的消息/模型抽象）产出行动；
   - 产出的行动仍走 `engine._is_legal` 双保险，非法则重试/回退——这条保护已经在 `act` 节点里就位。
   - 注入方式：`HeuristicPolicy(reasoner=LLMReasoner(...))` 或新建 `LLMPolicy`，其余调用方（SessionManager/CLI）无感知。

`langchain-core` 的角色：仅作为接 LLM 时的编排/消息基础（模型调用、prompt 模板、输出解析），
当前未使用，随 `ai` extra 与 LLM 推理节点一起引入。

---

## 5. 依赖与影响面

- **运行时依赖？** 否。`uv sync`（默认/含 dev/storage/api）都不装 langgraph/langchain。
- **被谁依赖？** 仅"未来的 LLM 推理节点"。引擎、记忆、联机、规则管线、CLI 全部**不依赖**它们。
- **架构保证**：`test_engine_does_not_import_network_or_llm` 持续守护"引擎纯逻辑、不碰 LLM"，
  确保即便接入 LangGraph，也只发生在 `agents` 层，不污染引擎。

---

## 相关文件
- 接缝与参考实现：`apps/backend/app/agents/decision_graph.py`
- 依赖声明：`apps/backend/pyproject.toml`（`[project.optional-dependencies].ai`）
- 设计：`docs/Start.md` §10（编排）/ §11（引擎契约）
- 实现与联动：`.review/detailed/07-phase2-5-implementation.md`（二、AI 决策子图）
