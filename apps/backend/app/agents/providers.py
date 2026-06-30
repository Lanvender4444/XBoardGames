"""LLM provider 工厂与预设（支持主流开源/闭源模型 API）。

"支持所有主流模型"的标准做法：绝大多数厂商都提供 **OpenAI 兼容**端点（只需 base_url + api_key + model），
所以本模块用一个 OpenAI 兼容适配器覆盖它们，另加 Anthropic 原生适配与离线默认模型。

覆盖示例（均为 OpenAI 兼容）：OpenAI、DeepSeek、Moonshot(Kimi)、智谱 GLM、通义千问(DashScope 兼容模式)、
OpenRouter、Groq、Together、Mistral、本地 Ollama / LM Studio / vLLM；以及 Anthropic(原生) / custom(自填 base_url)。
"""
from __future__ import annotations

from typing import Optional

from langchain_core.language_models.chat_models import BaseChatModel

# provider -> 预设（base_url / 默认模型 / 是否需要 key）
PRESETS: dict[str, dict] = {
    "offline":    {"label": "离线(内置启发式，无需Key)", "base_url": None, "model": "local-heuristic", "needs_key": False, "kind": "offline"},
    "openai":     {"label": "OpenAI", "base_url": "https://api.openai.com/v1", "model": "gpt-4o-mini", "needs_key": True, "kind": "openai"},
    "deepseek":   {"label": "DeepSeek", "base_url": "https://api.deepseek.com/v1", "model": "deepseek-chat", "needs_key": True, "kind": "openai"},
    "moonshot":   {"label": "Moonshot (Kimi)", "base_url": "https://api.moonshot.cn/v1", "model": "moonshot-v1-8k", "needs_key": True, "kind": "openai"},
    "zhipu":      {"label": "智谱 GLM", "base_url": "https://open.bigmodel.cn/api/paas/v4", "model": "glm-4-flash", "needs_key": True, "kind": "openai"},
    "qwen":       {"label": "通义千问 (DashScope)", "base_url": "https://dashscope.aliyuncs.com/compatible-mode/v1", "model": "qwen-plus", "needs_key": True, "kind": "openai"},
    "openrouter": {"label": "OpenRouter", "base_url": "https://openrouter.ai/api/v1", "model": "openai/gpt-4o-mini", "needs_key": True, "kind": "openai"},
    "groq":       {"label": "Groq", "base_url": "https://api.groq.com/openai/v1", "model": "llama-3.1-8b-instant", "needs_key": True, "kind": "openai"},
    "together":   {"label": "Together", "base_url": "https://api.together.xyz/v1", "model": "meta-llama/Llama-3.1-8B-Instruct-Turbo", "needs_key": True, "kind": "openai"},
    "mistral":    {"label": "Mistral", "base_url": "https://api.mistral.ai/v1", "model": "mistral-small-latest", "needs_key": True, "kind": "openai"},
    "ollama":     {"label": "Ollama (本地)", "base_url": "http://localhost:11434/v1", "model": "llama3.1", "needs_key": False, "kind": "openai"},
    "lmstudio":   {"label": "LM Studio (本地)", "base_url": "http://localhost:1234/v1", "model": "local-model", "needs_key": False, "kind": "openai"},
    "vllm":       {"label": "vLLM (本地/自建)", "base_url": "http://localhost:8000/v1", "model": "served-model", "needs_key": False, "kind": "openai"},
    "anthropic":  {"label": "Anthropic Claude", "base_url": None, "model": "claude-3-5-sonnet-latest", "needs_key": True, "kind": "anthropic"},
    "custom":     {"label": "自定义 (OpenAI 兼容)", "base_url": "", "model": "", "needs_key": False, "kind": "openai"},
}


def list_providers() -> list[dict]:
    """给前端的 provider 清单（含默认 base_url/model，便于下拉选择后自动填充）。"""
    out = []
    for key, p in PRESETS.items():
        out.append({
            "id": key, "label": p["label"], "base_url": p["base_url"] or "",
            "default_model": p["model"], "needs_key": p["needs_key"], "kind": p["kind"],
        })
    return out


# 进程级运行期配置（前端可改）
_runtime: dict = {"provider": "offline"}


def set_runtime_config(config: dict) -> dict:
    """设置当前对局使用的 LLM 配置（不持久化 api_key 到磁盘）。返回脱敏后的配置。"""
    global _runtime
    _runtime = dict(config or {"provider": "offline"})
    return public_config()


def get_runtime_config() -> dict:
    return dict(_runtime)


def public_config() -> dict:
    """脱敏配置（隐藏 api_key），用于回显。"""
    c = dict(_runtime)
    if c.get("api_key"):
        c["api_key"] = "***" + c["api_key"][-4:] if len(c.get("api_key", "")) >= 4 else "***"
        c["has_key"] = True
    else:
        c["has_key"] = False
    return c


def build_chat_model(config: Optional[dict] = None) -> BaseChatModel:
    """按配置构造 ChatModel。

    config: {provider, base_url?, api_key?, model?, temperature?}。缺省读运行期配置。
    - offline / 缺 key 的需 key provider → 内置离线模型（保证总能运行）。
    - anthropic → ChatAnthropic（需 langchain-anthropic）。
    - 其余 → OpenAI 兼容 ChatOpenAI(base_url, api_key, model)。
    """
    from app.agents.llm import LocalHeuristicChatModel  # 避免循环导入

    cfg = config if config is not None else get_runtime_config()
    provider = (cfg.get("provider") or "offline").lower()
    preset = PRESETS.get(provider, PRESETS["custom"])
    api_key = cfg.get("api_key") or ""
    base_url = cfg.get("base_url") or preset.get("base_url") or ""
    model = cfg.get("model") or preset.get("model") or "gpt-4o-mini"
    temperature = float(cfg.get("temperature", 0.7))

    if provider == "offline" or preset.get("kind") == "offline":
        return LocalHeuristicChatModel()
    if preset.get("needs_key") and not api_key:
        # 需要 key 却没给 → 回退离线，避免运行期报错
        return LocalHeuristicChatModel()

    if preset.get("kind") == "anthropic":
        try:
            from langchain_anthropic import ChatAnthropic
        except ImportError:
            return LocalHeuristicChatModel()  # 未装 langchain-anthropic → 离线兜底
        return ChatAnthropic(model=model, api_key=api_key, temperature=temperature)

    # OpenAI 兼容（覆盖绝大多数主流厂商 + 本地推理服务）
    try:
        from langchain_openai import ChatOpenAI
    except ImportError:
        return LocalHeuristicChatModel()  # 未装 langchain-openai → 离线兜底
    # 构造错误（如非法 base_url）按原样抛出，便于前端看到真实原因
    return ChatOpenAI(
        model=model,
        base_url=base_url or None,
        api_key=api_key or "not-needed",
        temperature=temperature,
    )
