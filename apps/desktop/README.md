# desktop — Tauri + React 桌面外壳（占位骨架）

见 Start.md §2 / §3。当前仅含目录与组件占位，待 Phase 2+ 填充。

- `src/features/lobby`  — 大厅 / 房间发现
- `src/features/table`  — 牌桌主界面
- `src/features/cards`  — 人物卡 / 羁绊图 / 记忆查看
- `src/features/rules`  — 规则文书上传与 Rule.md 编辑器
- `src/net`             — WebSocket 客户端 + 协议类型
- `src/store`           — 前端状态（zustand）
- `src-tauri`           — Rust：窗口、sidecar 启动、LAN 发现（mDNS/UDP）
