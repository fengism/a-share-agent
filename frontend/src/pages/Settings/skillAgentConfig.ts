import {
  resolveCapabilityPreset,
  type CapabilityPresetId,
} from "../../utils/capabilityPresets";

export {
  CAPABILITY_PRESETS,
} from "../../utils/capabilityPresets";
export type { CapabilityPresetId } from "../../utils/capabilityPresets";

export function updateDisabledNames(
  catalogNames: string[],
  disabledNames: string[],
  changedName: string,
  enabled: boolean,
): string[] {
  const disabled = new Set(disabledNames);
  if (enabled) disabled.delete(changedName);
  else disabled.add(changedName);
  return catalogNames.filter((name) => disabled.has(name));
}

export function applyCapabilityPreset(
  presetId: CapabilityPresetId,
  skillNames: string[],
  agentNames: string[],
) {
  const selection = resolveCapabilityPreset(presetId, skillNames, agentNames);
  const activeSkillNames = new Set(selection.skillNames);
  const activeAgentNames = new Set(selection.agentNames);
  return {
    disabled_chat_skills: skillNames.filter((name) => !activeSkillNames.has(name)),
    disabled_chat_agents: agentNames.filter((name) => !activeAgentNames.has(name)),
  };
}
