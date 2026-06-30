# LLM / LangChain 决策实现报告（AI 操控 AI 角色）

> 平台核心是"AI 操控 AI 角色"，因此 **AI 角色的每个行动都由 LLM 决策链产生**，langchain 已成为
> **核心（必需）依赖**，不再可选。本报告说明怎么用 langchain 实现、它在系统里处于什么位置、怎么验证、怎么接真模型。
>
> 验证：`uv run pytest` → **87 passed**（含 9 个 LLM 用例）；`autoplay --policy llm` 全 AI 整局收敛、
> 狼零次误伤队友；决策链确为 `ChatPromptTemplate | ChatModel | StrOutputParser`（LCEL `RunnableSequence`）。

---

## 1. langchain 现在是核心依赖

`pyproject.toml` 把 `langchain-core` 与 `langgraph` 从可选 `ai` extra **移入核心 `dependencies`**：

```toml
dependencies = [
    "pyyaml>=6.0",
    "langchain-core>=0.3",   # AI 决策链（必需）
    "langgraph>=0.2",        # AI 决策子图（必需）
]
[project.optional-dependencies]
ai = ["langchain-openai>=0.2"]   # 只有"真实 LLM provider"才可选
```

含义：`uv sync` 默认就装 langchain-core + langgraph；AI 角色开箱即由 LLM 决策链操控。
只有想接 OpenAI 等**真实模型**时才 `uv sync --extra ai` 并设环境变量。

---

## 2. 决策链怎么用 langchain 实现（`app/agents/llm.py`）

一条标准 LCEL 链：**prompt → chat model → 输出解析**。

```python
prompt = ChatPromptTemplate.from_messages([("system", _SYSTEM), ("human", _HUMAN)])
self.chain = prompt | self.model | StrOutputParser()      # RunnableSequence
...
out = self.chain.invoke({                                  # 把情境喂给 LLM
    "persona": ..., "phase": ..., "role": ..., "faction": ...,
    "beliefs": <STM 心证>, "bias": <羁绊偏置>, "memories": <LTM 召回>,
    "candidates": "[0] vote 目标#3 | 提示分 22.5\n[1] ...",
})
idx = _first_int(out)                                      # 解析 LLM 选的编号
chosen = legal[idx]                                        # 落地（再过引擎合法性双保险）
```

- **prompt**：把感知/召回得到的情境（身份、合法候选行动、对他人的心证、羁绊偏置、召回的长期记忆、人物卡 persona）
  渲染进 system+human 模板。
- **model**：见第 3 节。
- **parser**：`StrOutputParser` 取文本，再抽取整数编号；越界/解析失败回退启发式最优（鲁棒）。
- **合法性双保险**：LLM 选的行动仍过引擎 `_is_legal` 校验，防"幻觉"非法操作（§10）。

### 接缝：`LLMReasoner` 实现 `Reasoner` 协议
决策链被包成 `LLMReasoner.score()`：每次决策只调用一次 LLM 选编号并缓存，被选行动给高分、其余 0 分。
因此它能**直接插进 LangGraph / 纯 Python 决策子图的 reason 节点**——AI 决策真正由 LLM 产出。

---

## 3. ChatModel：默认离线、可换真实模型（`get_chat_model`）

为了"无 API key 也能整局运行 + 可单测"，默认提供一个**真实的 langchain `BaseChatModel`** ——
`LocalHeuristicChatModel`：

```python
class LocalHeuristicChatModel(BaseChatModel):   # 合法的 langchain ChatModel
    def _generate(self, messages, ...):
        idx = _argmax_hint(messages[-1].content)  # 读候选里的"提示分"挑最优
        return ChatResult(generations=[ChatGeneration(message=AIMessage(content=str(idx)))])
```

它是正经的 `BaseChatModel`，能进任何 LCEL 链；离线、确定性，让整条链路被真实执行与测试。

`get_chat_model()` 工厂：
- 设 `XBOARD_LLM_PROVIDER=openai` 且装了 `langchain-openai` → 返回 `ChatOpenAI`（读 `XBOARD_LLM_MODEL`）。
- 否则 → `LocalHeuristicChatModel`。
- 也可显式注入任意 `BaseChatModel`。

**换真模型零改动**：链（prompt|model|parser）、解析、合法性双保险都不变，只是 `model` 从本地换成 ChatOpenAI。

---

## 4. 在系统里的位置（与 LangGraph / 记忆协同）

```
AIPlayer（默认） → LLMPolicy
   └─ 跑 LangGraph 决策子图 build_decision_app(LLMReasoner)
        感知 → 召回(STM 心证 + 羁绊偏置 + LTM 召回) → 推理[LLM 决策链] → 行动(合法性双保险) → 编码
```

- `AIPlayer` 的默认策略现在是 `LLMPolicy`（"AI 操控 AI 角色"的体现）。
- `LLMPolicy` 默认在 **LangGraph 子图**里跑，推理节点用 `LLMReasoner`；langgraph 不可用时回退纯 Python 子图。
- 召回节点把 STM 心证 / 羁绊偏置 / LTM 记忆喂进 prompt → LLM 据此决策 → 形成"有记忆、有恩怨"的 AI 行为。
- 引擎仍是纯逻辑、不 import langchain（有纯净性测试守护）；LLM 只存在于 `agents` 层。

---

## 5. 四种策略对照

| 策略 | 决策方式 | 依赖 | 定位 |
|---|---|---|---|
| `LLMPolicy` | **LangGraph 子图 + langchain LLM 决策链** | 核心（langchain-core/langgraph） | **默认**：AI 操控 AI |
| `LangGraphPolicy` | LangGraph 子图 + 启发式推理 | 核心 | 无 LLM 的图执行 |
| `HeuristicPolicy` | 纯 Python 子图 + 启发式 | 无 | 基线/兜底 |
| `RandomPolicy` | 随机合法行动 | 无 | 烟测 |

四者满足同一 `Policy` 协议，可在 CLI / 联机中互换。`autoplay --policy llm` 即用 LLM 决策链跑全 AI 局。

---

## 6. 怎么运行与验证

```bash
cd apps/backend
uv sync                                   # 默认即装 langchain-core + langgraph
uv run pytest tests/test_llm.py -q        # 9 passed
uv run python -m app.cli.autoplay --game werewolf --players 8 --policy llm

# 接真实 LLM：
uv sync --extra ai
export XBOARD_LLM_PROVIDER=openai
export OPENAI_API_KEY=sk-...
export XBOARD_LLM_MODEL=gpt-4o-mini
uv run python -m app.cli.autoplay --policy llm
```

实测（离线默认模型）：6–8 局全收敛、狼零次误伤队友；`LLMReasoner.chain` 为 `RunnableSequence`；
默认 `model._llm_type == "local-heuristic"`；`AIPlayer().policy` 为 `LLMPolicy`。

---

## 7. 新增/改动文件
- 新增：`app/agents/llm.py`（LocalHeuristicChatModel / get_chat_model / LLMReasoner / LLMPolicy）、`tests/test_llm.py`。
- 改动：`app/agents/__init__.py`（导出 LLM 符号）、`app/agents/decision_graph.py`（AIPlayer 默认 LLMPolicy）、
  `app/cli/autoplay.py`（`--policy llm`）、`pyproject.toml`（langchain-core/langgraph 提为核心依赖）。

## 相关文档
- LangGraph 子图实现：`.review/langgraph决策子图实现报告.md`
- Phase 2–5 实现与联动：`.review/detailed/07-phase2-5-implementation.md`
- 设计：`docs/Start.md` §10
