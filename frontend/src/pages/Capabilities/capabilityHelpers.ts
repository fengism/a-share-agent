import type {
  ChatCapabilitiesResponse,
  SkillCapabilityInfo,
  ToolCapabilityInfo,
} from "../../types/capabilities";

function includesQuery(values: Array<string | undefined>, query: string): boolean {
  return values.some((value) => value?.toLocaleLowerCase().includes(query));
}

export function filterCapabilities(
  capabilities: ChatCapabilitiesResponse,
  rawQuery: string,
): { skills: SkillCapabilityInfo[]; tools: ToolCapabilityInfo[] } {
  const query = rawQuery.trim().toLocaleLowerCase();
  if (!query) return { skills: capabilities.skills, tools: capabilities.tools };

  const skills = capabilities.skills.filter((skill) => includesQuery([
    skill.name,
    skill.description,
    ...skill.triggers,
    ...skill.rules,
    ...skill.exclusions,
    ...skill.tool_names,
  ], query));
  const tools = capabilities.tools.filter((tool) => includesQuery([
    tool.name,
    tool.description,
    tool.policy.cost,
    tool.policy.freshness,
    ...tool.skill_names,
    ...Object.keys(tool.parameters.properties),
  ], query));

  return { skills, tools };
}

export function formatCacheTtl(seconds: number): string {
  if (seconds <= 0) return "不缓存";
  if (seconds < 60) return `${seconds} 秒`;
  if (seconds < 3600) return `${Math.round(seconds / 60)} 分钟`;
  return `${Math.round(seconds / 3600)} 小时`;
}

export function formatToolTimeout(seconds?: number | null): string {
  if (seconds == null) return "跟随全局";
  if (seconds < 60) return `${seconds} 秒`;
  return `${Math.round(seconds / 60)} 分钟`;
}
