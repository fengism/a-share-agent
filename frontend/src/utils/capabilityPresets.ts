export type CapabilityPresetId = "full" | "quick" | "news" | "low_cost";

export const CAPABILITY_PRESETS: Array<{
  id: CapabilityPresetId;
  label: string;
  description: string;
}> = [
  { id: "full", label: "全面研究", description: "启用全部 Skill 与 Agent" },
  { id: "quick", label: "快速分析", description: "聚焦个股、选股和市场数据" },
  { id: "news", label: "资讯追踪", description: "聚焦网页、资讯、行业和宏观" },
  { id: "low_cost", label: "低成本", description: "保留全部 Skill，关闭多 Agent" },
];

const PRESET_ACTIVE_SKILLS: Record<CapabilityPresetId, "all" | string[]> = {
  full: "all",
  quick: ["stock_analysis", "stock_screening", "market_data"],
  news: ["url_content", "twitter_account", "industry_research", "information_query"],
  low_cost: "all",
};

const PRESET_ACTIVE_AGENTS: Record<CapabilityPresetId, "all" | string[]> = {
  full: "all",
  quick: ["technical", "fundamental"],
  news: ["news", "macro"],
  low_cost: [],
};

function selectPresetNames(catalogNames: string[], activeNames: "all" | string[]): string[] {
  if (activeNames === "all") return [...catalogNames];
  const active = new Set(activeNames);
  return catalogNames.filter((name) => active.has(name));
}

export function resolveCapabilityPreset(
  presetId: CapabilityPresetId,
  skillNames: string[],
  agentNames: string[],
) {
  return {
    skillNames: selectPresetNames(skillNames, PRESET_ACTIVE_SKILLS[presetId]),
    agentNames: selectPresetNames(agentNames, PRESET_ACTIVE_AGENTS[presetId]),
  };
}
