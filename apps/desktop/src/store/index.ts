// 前端状态（zustand）：SSE 串行驱动对局 + 流式发言 + 思维调试 + LLM 配置。见 app/api/play.py。
import { create } from "zustand";
import { api, backendUrl, setBackendUrl, type GameView, type Provider, type LLMConfig } from "../api";

export type ViewKey = "lobby" | "table" | "cards" | "settings";

export interface LiveSpeech {
  seat: number;
  persona: string;
  text: string;
}

export interface AppState {
  view: ViewKey;
  setView: (v: ViewKey) => void;

  game: GameView | null;
  loading: boolean;
  error: string | null;
  players: number;
  createGame: () => Promise<void>;
  submit: (type: string, targets: number[], text?: string) => Promise<void>;
  leave: () => void;
  setPlayers: (n: number) => void;

  thinking: number | null;
  live: LiveSpeech | null;
  thoughts: Record<string, unknown>;
  debug: boolean;
  toggleDebug: () => void;

  providers: Provider[];
  llm: LLMConfig;
  backend: string;
  loadProviders: () => Promise<void>;
  setBackend: (u: string) => void;
  setLLMField: (k: keyof LLMConfig, v: string | number) => void;
  saveLLM: () => Promise<void>;
  testInfo: string | null;
  testBackend: () => Promise<void>;
  testLLM: () => Promise<void>;
}

let es: EventSource | null = null;

export const useApp = create<AppState>((set, get) => {
  function closeStream() {
    if (es) { es.close(); es = null; }
  }

  function appendEvent(ev: GameView["log"][number]) {
    const g = get().game;
    if (!g) return;
    if (g.log.some((e) => e.seq === ev.seq)) return;
    set({ game: { ...g, log: [...g.log, ev] } });
  }

  function startStream() {
    const g = get().game;
    if (!g) return;
    closeStream();
    set({ thinking: null, live: null });
    es = new EventSource(api.streamUrl(g.game_id));
    es.onmessage = (e) => {
      let f: any;
      try { f = JSON.parse(e.data); } catch { return; }
      switch (f.type) {
        case "thinking":
          set({ thinking: f.seat });
          break;
        case "thought":
          set({ thoughts: { ...get().thoughts, [String(f.seat)]: f.thought } });
          break;
        case "speak_start":
          set({ live: { seat: f.seat, persona: f.persona, text: "" }, thinking: null });
          break;
        case "speak_delta": {
          const cur = get().live;
          if (cur && cur.seat === f.seat) set({ live: { ...cur, text: cur.text + f.delta } });
          break;
        }
        case "speak_end":
          set({ live: null });
          break;
        case "event":
          appendEvent(f.event);
          break;
        case "your_turn":
        case "game_over":
          closeStream();
          set({ game: f.view, thinking: null, live: null });
          break;
      }
    };
    es.onerror = () => {
      closeStream();
      const gg = get().game;
      if (gg) api.view(gg.game_id, gg.your_seat).then((game) => set({ game })).catch(() => {});
    };
  }

  return {
    view: "lobby",
    setView: (v) => set({ view: v }),

    game: null,
    loading: false,
    error: null,
    players: 8,
    setPlayers: (n) => set({ players: Math.max(6, Math.min(12, n)) }),

    thinking: null,
    live: null,
    thoughts: {},
    debug: false,
    toggleDebug: () => set({ debug: !get().debug }),

    createGame: async () => {
      set({ loading: true, error: null, thoughts: {}, live: null, thinking: null });
      try {
        const game = await api.createGame({ slug: "werewolf", players: get().players, human_seats: [0], stream: true });
        set({ game, view: "table" });
        startStream();
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
        const game = await api.act(g.game_id, { seat: g.your_seat, type, targets, extra, stream: true });
        set({ game });
        startStream();
      } catch (e) {
        set({ error: String((e as Error).message) });
      } finally {
        set({ loading: false });
      }
    },
    leave: () => {
      closeStream();
      set({ game: null, view: "lobby", thoughts: {}, live: null, thinking: null });
    },

    providers: [],
    llm: { provider: "offline", base_url: "", api_key: "", model: "", temperature: 0.7 },
    backend: backendUrl(),
    testInfo: null,
    loadProviders: async () => {
      try {
        const [{ providers }, llm] = await Promise.all([api.providers(), api.getLLM()]);
        set({ providers, llm: { ...get().llm, ...llm } });
      } catch (e) {
        set({ error: String((e as Error).message) });
      }
    },
    setBackend: (u) => { setBackendUrl(u); set({ backend: u }); },
    setLLMField: (k, v) => set({ llm: { ...get().llm, [k]: v } }),
    saveLLM: async () => {
      set({ loading: true, error: null });
      try {
        const saved = await api.setLLM(get().llm);
        set({ llm: { ...get().llm, ...saved, api_key: "" }, testInfo: "已保存。点“测试模型连接”验证。" });
      } catch (e) {
        set({ error: String((e as Error).message) });
      } finally {
        set({ loading: false });
      }
    },
    testBackend: async () => {
      set({ testInfo: "测试后端连接中…", error: null });
      try {
        const h = await api.health();
        set({ testInfo: `后端连接正常（${get().backend}）：${h.status}` });
      } catch (e) {
        set({ testInfo: `后端连接失败：${String((e as Error).message)}` });
      }
    },
    testLLM: async () => {
      set({ testInfo: "测试模型连接中…", error: null });
      try {
        const r = await api.testLLM(get().llm);
        const tail = (r as any).hint ? "\n提示：" + (r as any).hint : "";
        set({ testInfo: r.ok ? `模型可用（${r.model_class}）：${r.note}｜样例「${r.sample}」` : `模型连接失败：${r.error}${tail}` });
      } catch (e) {
        set({ testInfo: `模型测试失败：${String((e as Error).message)}` });
      }
    },
  };
});
