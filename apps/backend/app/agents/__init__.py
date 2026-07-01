"""AI 玩家与对局编排（Start.md §10）——共享 State · 并发 Think · 顺序 Act。

- **内层（单个 agent 的"思考"）**：决策子图 感知→召回→推理→行动→编码。
  - 纯 Python：``DecisionGraph`` / ``HeuristicPolicy`` / ``RandomPolicy``。
  - LangGraph：``LangGraphPolicy`` / ``build_decision_app``。
  - LLM 驱动（默认）：``LLMPolicy`` / ``LLMReasoner`` / ``get_chat_model``（langchain 决策链）。
- **外层（多 agent 的"编排"）**：``orchestrator`` —— 按阶段分
  **抢占式 PREEMPTIVE**（并发思考→引擎顺序仲裁）与 **排队式 QUEUED**（轮流发言）。
  - ``drive``：人机/全 AI 通用步进（轮到人类暂停）。
  - ``run_orchestrator`` / ``build_orchestrator``：LangGraph 编排图（抢占式用 ``Send`` 并发）。
"""

from app.agents.decision_graph import (
    AIPlayer,
    DecisionGraph,
    GraphContext,
    HeuristicPolicy,
    HeuristicReasoner,
    Policy,
    RandomPolicy,
    Reasoner,
)
from app.agents.langgraph_graph import (
    DecisionState,
    LangGraphPolicy,
    build_decision_app,
    langgraph_available,
)
from app.agents.llm import (
    LLMPolicy,
    LLMReasoner,
    LocalHeuristicChatModel,
    get_chat_model,
)
from app.agents.orchestrator import (
    PREEMPTIVE,
    QUEUED,
    build_orchestrator,
    drive,
    phase_mode,
    run_orchestrator,
    step_preemptive,
    step_queued,
    utterance,
)

__all__ = [
    # 内层：单 agent 思考
    "DecisionGraph",
    "AIPlayer",
    "Policy",
    "RandomPolicy",
    "HeuristicPolicy",
    "HeuristicReasoner",
    "Reasoner",
    "GraphContext",
    "LangGraphPolicy",
    "build_decision_app",
    "langgraph_available",
    "DecisionState",
    "LLMPolicy",
    "LLMReasoner",
    "LocalHeuristicChatModel",
    "get_chat_model",
    # 外层：多 agent 编排
    "phase_mode",
    "PREEMPTIVE",
    "QUEUED",
    "drive",
    "run_orchestrator",
    "build_orchestrator",
    "step_preemptive",
    "step_queued",
    "utterance",
]
