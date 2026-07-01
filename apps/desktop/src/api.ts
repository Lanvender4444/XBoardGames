// 后端 API 客户端（可配置后端地址）。见 app/api/play.py。
const BACKEND_KEY = "xboard.backend";
const DEFAULT_BACKEND = "http://localhost:8000";

export function backendUrl(): string {
  return (typeof localStorage !== "undefined" && localStorage.getItem(BACKEND_KEY)) || DEFAULT_BACKEND;
}
export function setBackendUrl(u: string): void {
  if (typeof localStorage !== "undefined") localStorage.setItem(BACKEND_KEY, u);
}

async function call<T>(path: string, opts: RequestInit = {}): Promise<T> {
  let res: Response;
  try {
    res = await fetch(backendUrl() + path, {
      headers: { "Content-Type": "application/json" },
      ...opts,
    });
  } catch {
    throw new Error(`无法连接后端 ${backendUrl()} —— 后端是否已启动？（cd apps/backend && uv run uvicorn "app.api.app:create_app" --factory --port 8000），或“设置”里的后端地址是否正确？`);
  }
  if (!res.ok) {
    let detail = res.statusText;
    try {
      detail = (await res.json()).detail ?? detail;
    } catch {
      /* ignore */
    }
    throw new Error(typeof detail === "string" ? detail : JSON.stringify(detail));
  }
  return res.json() as Promise<T>;
}

export interface Provider {
  id: string;
  label: string;
  base_url: string;
  default_model: string;
  needs_key: boolean;
  kind: string;
}

export interface LLMConfig {
  provider: string;
  base_url?: string;
  api_key?: string;
  model?: string;
  temperature?: number;
  has_key?: boolean;
}

export interface ActionVM {
  seat: number;
  type: string;
  targets: number[];
  label: string;
}

export interface SeatVM {
  seat: number;
  name: string;
  alive: boolean;
  actor_type: string;
  role: string | null;
  faction: string | null;
}

export interface EventVM {
  seq: number;
  phase: string;
  round: number;
  actor: number | null;
  action: string;
  payload: Record<string, unknown>;
  visibility: string;
}

export interface GameView {
  game_id: string;
  slug: string;
  phase: string;
  round: number;
  finished: boolean;
  winner: string | null;
  your_seat: number;
  your_role: string | null;
  your_faction: string | null;
  your_turn: boolean;
  your_actions: ActionVM[];
  awaiting: number[];
  seats: SeatVM[];
  log: EventVM[];
  personas?: Record<string, { name: string; traits: string[]; style: string }>;
  thoughts?: Record<string, any>;
}

export const api = {
  health: () => call<{ status: string }>("/health"),
  providers: () => call<{ providers: Provider[] }>("/providers"),
  getLLM: () => call<LLMConfig>("/llm/config"),
  setLLM: (cfg: LLMConfig) => call<LLMConfig>("/llm/config", { method: "POST", body: JSON.stringify(cfg) }),
  testLLM: (cfg: LLMConfig) => call<{ ok: boolean; error?: string; hint?: string; sample?: string; note?: string; model_class?: string }>(
    "/llm/test", { method: "POST", body: JSON.stringify(cfg) }),
  createGame: (body: { slug: string; players: number; human_seats: number[]; seed?: number | null; stream?: boolean }) =>
    call<GameView>("/games", { method: "POST", body: JSON.stringify(body) }),
  streamUrl: (gid: string) => backendUrl() + `/games/${gid}/stream`,
  view: (gid: string, seat: number) => call<GameView>(`/games/${gid}?seat=${seat}`),
  act: (gid: string, action: { seat: number; type: string; targets: number[]; extra?: Record<string, unknown>; stream?: boolean }) =>
    call<GameView>(`/games/${gid}/action`, { method: "POST", body: JSON.stringify(action) }),
};
