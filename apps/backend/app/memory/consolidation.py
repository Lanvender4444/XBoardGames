"""局结束记忆固化（Start.md §8.4，Phase 2 占位）。

一局结束触发后台任务：
1. 从 STM + 事件日志中用 LLM 提炼"本局值得长期记住的若干条"。
2. 写入 LTM（语义 + 情景），生成 embedding 入向量库，设 salience。
3. 根据共同经历更新所有相关羁绊。
4. 清理本局 STM。
"""
from __future__ import annotations


def consolidate_session(session_id: int) -> None:
    raise NotImplementedError("记忆固化待 Phase 2 接入")
