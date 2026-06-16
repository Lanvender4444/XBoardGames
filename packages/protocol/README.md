# protocol

前后端共享的通信协议 schema（单一定义，生成 TS 与 Python 类型，避免漂移）。
见 Start.md §12。消息信封：`{ "type", "session_id", "seq", "payload" }`。

- `messages.ts` — TypeScript 端类型（前端 import）
- 后端对应类型见 `apps/backend/app/api/protocol.py`（当前手写镜像，后续可由本 schema 代码生成）
