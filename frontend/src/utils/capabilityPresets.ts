/**
 * 前端能力预设。
 *
 * 这里的 skill / agent 名是**硬编码**的，必须与后端能力目录保持一致。后端改名或
 * 下线某项能力时，预设会静默残缺（用户点了「快速分析」，拿到的却少了预期的一项），
 * 界面上完全看不出来。因此提供 {@link reportPresetCatalogDrift}，在拿到完整目录时
 * 主动校验并告警。
 *
 * 注意区分两种「名字不在目录里」：
 * - **契约漂移**：预设写错了名字，需要改代码 → 用 {@link reportPresetCatalogDrift}；
 * - **按需过滤**：调用方按可用性 / 用户开关筛过目录（Chat 预设条即如此），缺名属预期，
 *   因此 {@link resolveCapabilityPreset} 只把情况放进返回值，不主动告警。
 */

export type CapabilityPresetId = "full" | "quick" | "news" | "low_cost";

export interface CapabilityPresetMeta {
  id: CapabilityPresetId;
  label: string;
  description: string;
}

export const CAPABILITY_PRESETS: CapabilityPresetMeta[] = [
  { id: "full", label: "全面研究", description: "启用全部 Skill 与 Agent" },
  { id: "quick", label: "快速分析", description: "聚焦个股、选股和市场数据" },
  { id: "news", label: "资讯追踪", description: "聚焦网页、资讯、行业和宏观" },
  { id: "low_cost", label: "低成本", description: "保留全部 Skill，关闭多 Agent" },
];

/** `"all"` 表示启用目录里全部能力；空数组表示全部关闭（`low_cost` 的 agent 即此意）。 */
type PresetSelectionRule = "all" | readonly string[];

const PRESET_ACTIVE_SKILLS: Record<CapabilityPresetId, PresetSelectionRule> = {
  full: "all",
  quick: ["stock_analysis", "stock_screening", "market_data"],
  news: ["url_content", "twitter_account", "industry_research", "information_query"],
  low_cost: "all",
};

const PRESET_ACTIVE_AGENTS: Record<CapabilityPresetId, PresetSelectionRule> = {
  full: "all",
  quick: ["technical", "fundamental"],
  news: ["news", "macro"],
  low_cost: [],
};

export interface CapabilityPresetResolution {
  skillNames: string[];
  agentNames: string[];
  /** 预设声明、但传入目录里没有的名字，形如 `skill:stock_analysis`。 */
  unresolvedNames: string[];
}

export interface PresetCatalogDrift {
  presetId: CapabilityPresetId;
  unresolvedNames: string[];
}

interface SelectionOutcome {
  selected: string[];
  unresolved: string[];
}

function selectPresetNames(catalogNames: string[], rule: PresetSelectionRule): SelectionOutcome {
  if (rule === "all") return { selected: [...catalogNames], unresolved: [] };
  const catalog = new Set(catalogNames);
  return {
    selected: catalogNames.filter((name) => rule.includes(name)),
    unresolved: rule.filter((name) => !catalog.has(name)),
  };
}

/**
 * 按预设挑出应启用的能力名。
 *
 * 纯函数：只做集合运算，不产生副作用，因此可安全地在 render 中反复调用。
 *
 * Param:
 *   presetId: 预设 id
 *   skillNames / agentNames: 候选名列表（可以是完整目录，也可以是过滤后的子集）
 * Return:
 *   选中项与「传入目录里没有的名字」
 */
export function resolveCapabilityPreset(
  presetId: CapabilityPresetId,
  skillNames: string[],
  agentNames: string[],
): CapabilityPresetResolution {
  const skills = selectPresetNames(skillNames, PRESET_ACTIVE_SKILLS[presetId]);
  const agents = selectPresetNames(agentNames, PRESET_ACTIVE_AGENTS[presetId]);
  return {
    skillNames: skills.selected,
    agentNames: agents.selected,
    unresolvedNames: [
      ...skills.unresolved.map((name) => `skill:${name}`),
      ...agents.unresolved.map((name) => `agent:${name}`),
    ],
  };
}

/**
 * 对照**完整**能力目录，列出各预设引用不到的名字。
 *
 * Param:
 *   skillNames / agentNames: 完整能力目录（不可传过滤后的子集，否则会误报）
 * Return:
 *   存在漂移的预设列表；全部正常时为空数组
 */
export function describePresetCatalogDrift(
  skillNames: string[],
  agentNames: string[],
): PresetCatalogDrift[] {
  const drifts: PresetCatalogDrift[] = [];
  for (const preset of CAPABILITY_PRESETS) {
    const { unresolvedNames } = resolveCapabilityPreset(preset.id, skillNames, agentNames);
    if (unresolvedNames.length > 0) {
      drifts.push({ presetId: preset.id, unresolvedNames });
    }
  }
  return drifts;
}

const reportedDrift = new Set<string>();

/**
 * 校验并告警预设契约漂移；同一 preset+name 只告警一次。
 *
 * Param:
 *   skillNames / agentNames: 完整能力目录
 * Return:
 *   本次新发现的漂移（已被历史告警覆盖的不再返回），无漂移时为空数组
 */
export function reportPresetCatalogDrift(
  skillNames: string[],
  agentNames: string[],
): PresetCatalogDrift[] {
  const fresh: PresetCatalogDrift[] = [];
  for (const drift of describePresetCatalogDrift(skillNames, agentNames)) {
    const unseen = drift.unresolvedNames.filter(
      (name) => !reportedDrift.has(`${drift.presetId}/${name}`),
    );
    if (unseen.length === 0) continue;
    for (const name of unseen) reportedDrift.add(`${drift.presetId}/${name}`);
    fresh.push({ presetId: drift.presetId, unresolvedNames: unseen });
  }
  if (fresh.length === 0) return [];

  const detail = fresh.map((drift) => `${drift.presetId}(${drift.unresolvedNames.join(", ")})`).join("；");
  console.warn(
    `[capabilityPresets] 能力预设引用了后端能力目录中不存在的名称，该预设会静默残缺：${detail}。` +
      "请同步 src/utils/capabilityPresets.ts 与后端能力目录。",
  );
  return fresh;
}
