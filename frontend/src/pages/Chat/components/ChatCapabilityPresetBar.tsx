import { Button, Space, Typography } from "antd";
import type {
  ChatCapabilitiesResponse,
  ChatCapabilityAvailabilityResponse,
} from "../../../types/capabilities";
import {
  CAPABILITY_PRESETS,
  resolveCapabilityPreset,
  type CapabilityPresetId,
} from "../../../utils/capabilityPresets";

const { Text } = Typography;

interface ChatCapabilityPresetBarProps {
  capabilities?: ChatCapabilitiesResponse;
  availability?: ChatCapabilityAvailabilityResponse;
  disabledSkillNames: string[];
  disabledAgentNames: string[];
  skillNames: string[] | null;
  agentNames: string[] | null;
  onApply: (skillNames: string[], agentNames: string[]) => void;
  disabled: boolean;
}

function sameNames(left: string[], right: string[]): boolean {
  return left.length === right.length && left.every((name, index) => name === right[index]);
}

export function ChatCapabilityPresetBar({
  capabilities,
  availability,
  disabledSkillNames,
  disabledAgentNames,
  skillNames,
  agentNames,
  onApply,
  disabled,
}: ChatCapabilityPresetBarProps) {
  if (!capabilities) return null;

  const disabledSkills = new Set(disabledSkillNames);
  const disabledAgents = new Set(disabledAgentNames);
  const selectableSkillNames = capabilities.skills
    .filter((skill) => {
      const status = availability?.skills[skill.name]?.status;
      return !disabledSkills.has(skill.name) && status !== "unavailable" && status !== "disabled";
    })
    .map((skill) => skill.name);
  const selectableAgentNames = capabilities.agents
    .filter((agent) => {
      const status = availability?.agents[agent.name]?.status;
      return !disabledAgents.has(agent.name) && status !== "unavailable" && status !== "disabled";
    })
    .map((agent) => agent.name);

  const activePresetId = skillNames !== null && agentNames !== null
    ? CAPABILITY_PRESETS.find((preset) => {
        const selection = resolveCapabilityPreset(
          preset.id,
          selectableSkillNames,
          selectableAgentNames,
        );
        return sameNames(skillNames, selection.skillNames)
          && sameNames(agentNames, selection.agentNames);
      })?.id
    : undefined;

  const applyPreset = (presetId: CapabilityPresetId) => {
    const selection = resolveCapabilityPreset(
      presetId,
      selectableSkillNames,
      selectableAgentNames,
    );
    onApply(selection.skillNames, selection.agentNames);
  };

  return (
    <div className="chat-capability-presets">
      <Text type="secondary">本会话预设</Text>
      <Space size={[6, 6]} wrap>
        {CAPABILITY_PRESETS.map((preset) => (
          <Button
            key={preset.id}
            size="small"
            type={activePresetId === preset.id ? "primary" : "default"}
            title={preset.description}
            disabled={disabled}
            onClick={() => applyPreset(preset.id)}
          >
            {preset.label}
          </Button>
        ))}
      </Space>
    </div>
  );
}
