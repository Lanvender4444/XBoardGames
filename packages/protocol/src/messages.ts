// 前后端共享协议类型（Start.md §12）。
// 注意：当前为手写定义；Phase 3 接入代码生成后由单一 schema 产出 TS + Python。

export interface Envelope<P = unknown> {
  type: string;
  session_id: string;
  seq: number;
  payload: P;
}

// 客户端 -> 服务器
export type ClientMessageType =
  | "join"
  | "leave"
  | "submit_action"
  | "chat"
  | "heartbeat";

// 服务器 -> 客户端
export type ServerMessageType =
  | "state_snapshot"
  | "state_patch"
  | "event"
  | "request_action"
  | "phase_changed"
  | "game_over"
  | "error";

export interface Action {
  seat: number;
  type: string; // 原语名：eliminate / investigate / vote / nominate / quest / speak ...
  target?: number | number[];
  channel?: string;
  extra?: Record<string, unknown>;
}

export interface RequestActionPayload {
  seat: number;
  legal_actions: Action[];
  deadline_ms: number;
}
