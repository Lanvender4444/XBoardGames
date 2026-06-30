// 前端状态（zustand）：接后端可玩对局 + LLM 配置。见 app/api/play.py。
import { create } from "zustand";
import { api, backendUrl, setBackendUrl, type GameView, type Provider, type LLMConfig } from "../api";

export type ViewKey = "lobby" | "table" | "cards" | "settings";

export interface AppState {
  view: ViewKey;
  setView: (v: ViewKey) => void;

  // 对局
  game: GameView | null;
  loading: boolean;
  error: string | null;
  players: number;
  createGame: () => Promise<void>;
  submit: (type: string, targets: number[], text?: string) => Promise<void>;
  refresh: () => Promise<void>;
  leave: () => void;
  setPlayers: (n: number) => void;

  // LLM 配置
  providers: Provider[];
  llm: LLMConfig;
  backend: string;
  loadProviders: () => Promise<void>;
  setBackend: (u: string) => void;
  setLLMField: (k: keyof LLMConfig, v: string | number) => void;
  saveLLM: () => Promise<void>;
}

export const useApp = create<AppState>((set, get) => ({
  view: "lobby",
  setView: (v) => set({ view: v }),

  game: null,
  loading: false,
  error: null,
  players: 8,
  setPlayers: (n) => set({ players: Math.max(6, Math.min(12, n)) }),

  createGame: async () => {
    set({ loading: true, error: null });
    try {
      const game = await api.createGame({ slug: "werewolf", players: get().players, human_seats: [0] });
      set({ game, view: "table" });
    } catch (e) {
      set({ error: String((e as Error).message) });
    } finally {
      set({ loading: false });
    }
  },
  submit: async (type, targets, text) => {
    const g = get().game;
    if (!g) return;
    set({ loading: true, error: null });
    try {
      const extra = text ? { text } : undefined;
      const game = await api.act(g.game_id, { seat: g.your_seat, type, targets, extra });
      set({ game });
    } catch (e) {
      set({ error: String((e as Error).message) });
    } finally {
      set({ loading: false });
    }
  },
  refresh: async () => {
    const g = get().game;
    if (!g) return;
    try {
      set({ game: await api.view(g.game_id, g.your_seat) });
    } catch (e) {
      set({ error: String((e as Error).message) });
    }
  },
  leave: () => set({ game: null, view: "lobby" }),

  providers: [],
  llm: { provider: "offline", base_url: "", api_key: "", model: "", temperature: 0.7 },
  backend: backendUrl(),
  loadProviders: async () => {
    try {
      const [{ providers }, llm] = await Promise.all([api.providers(), api.getLLM()]);
      set({ providers, llm: { ...get().llm, ...llm } });
    } catch (e) {
      set({ error: String((e as Error).message) });
    }
  },
  setBackend: (u) => {
    setBackendUrl(u);
    set({ backend: u });
  },
  setLLMField: (k, v) => set({ llm: { ...get().llm, [k]: v } }),
  saveLLM: async () => {
    set({ loading: true, error: null });
    try {
      const saved = await api.setLLM(get().llm);
      set({ llm: { ...get().llm, ...saved } });
    } catch (e) {
      set({ error: String((e as Error).message) });
    } finally {
      set({ loading: false });
    }
  },
}));
