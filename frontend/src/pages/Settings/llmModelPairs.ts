/** Provider 官方推荐的主模型 + 子模型配对与轻量模型清单。 */

export interface ModelPair {
  main: string;
  sub: string;
  label?: string;
}

export const PROVIDER_MODEL_PAIRS: Record<string, ModelPair> = {
  deepseek: {
    main: "deepseek-reasoner",
    sub: "deepseek-chat",
    label: "DeepSeek (R1 思考 + V3 快速)",
  },
  openai: {
    main: "gpt-4o",
    sub: "gpt-4o-mini",
    label: "OpenAI (GPT-4o + Mini)",
  },
  qwen: {
    main: "qwen-plus",
    sub: "qwen-turbo",
    label: "通义千问 (Plus + Turbo)",
  },
  zhipu: {
    main: "glm-4-plus",
    sub: "GLM-4.7-Flash",
    label: "智谱 (GLM-4 Plus + Flash)",
  },
  claude: {
    main: "anthropic/claude-sonnet-4-6",
    sub: "anthropic/claude-haiku-4-5",
    label: "Claude (Sonnet + Haiku)",
  },
  gemini: {
    main: "gemini/gemini-2.5-pro",
    sub: "gemini/gemini-2.5-flash",
    label: "Gemini (Pro + Flash)",
  },
  moonshot: {
    main: "moonshot-v1-32k",
    sub: "moonshot-v1-8k",
    label: "Moonshot (32k + 8k)",
  },
  openrouter: {
    main: "anthropic/claude-sonnet-4-6",
    sub: "openai/gpt-4o-mini",
    label: "OpenRouter 混配",
  },
  siliconflow: {
    main: "deepseek-ai/DeepSeek-R1",
    sub: "deepseek-ai/DeepSeek-V3",
    label: "硅基流动 (R1 + V3)",
  },
  ollama: {
    main: "deepseek-r1:8b",
    sub: "qwen2.5:7b",
    label: "Ollama 本地 (R1 + Qwen2.5)",
  },
};

export const PROVIDER_RECOMMENDED_SUB_MODELS: Record<string, string[]> = {
  deepseek: ["deepseek-chat", "deepseek-v4-flash"],
  openai: ["gpt-4o-mini", "gpt-5-mini"],
  claude: ["anthropic/claude-haiku-4-5"],
  gemini: ["gemini/gemini-2.5-flash"],
  qwen: ["qwen-turbo", "qwen-plus"],
  siliconflow: ["deepseek-ai/DeepSeek-V3", "Qwen/Qwen2.5-7B-Instruct"],
  ollama: ["qwen2.5:7b", "llama3.1:8b"],
  zhipu: ["GLM-4.7-Flash", "glm-4-air"],
  moonshot: ["moonshot-v1-8k"],
  openrouter: ["openai/gpt-4o-mini", "google/gemini-2.5-flash"],
  azure: [],
  custom: [],
};
