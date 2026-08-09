import { useState } from "react";
import { BranchesOutlined, RobotOutlined, SaveOutlined } from "@ant-design/icons";
import { Button, Card, Divider, Segmented, Space, Switch, Tag, Typography } from "antd";
import SectionDataState from "../../components/SectionDataState";
import { useColors, useStyles } from "../../styles/ui";
import type {
  CapabilityAvailabilityInfo,
  ChatCapabilitiesResponse,
  ChatCapabilityAvailabilityResponse,
} from "../../types/capabilities";
import type { ConfigUpdate } from "../../types/settings";
import {
  applyCapabilityPreset,
  CAPABILITY_PRESETS,
  updateDisabledNames,
} from "./skillAgentConfig";

const { Text } = Typography;

type CapabilityView = "skills" | "agents";

interface SkillAgentConfigCardProps {
  capabilities?: ChatCapabilitiesResponse;
  availability?: ChatCapabilityAvailabilityResponse;
  disabledSkillNames: string[];
  disabledAgentNames: string[];
  onChange: (patch: ConfigUpdate) => void;
  onSave: () => void;
  isSaving: boolean;
  isLoading?: boolean;
  error?: Error | null;
  onRetry?: () => void;
  isCheckingAvailability?: boolean;
  onCheckAvailability?: () => void;
}

const AVAILABILITY_META = {
  ready: { label: "可用", color: "green" },
  degraded: { label: "受限", color: "gold" },
  unavailable: { label: "不可用", color: "red" },
  disabled: { label: "已关闭", color: "default" },
} as const;

function AvailabilityStatus({ info }: { info?: CapabilityAvailabilityInfo }) {
  if (!info) return null;
  const meta = AVAILABILITY_META[info.status];
  return (
    <Space size={6} wrap>
      <Tag color={meta.color}>{meta.label}</Tag>
      <Text style={{ color: "inherit", fontSize: 12 }}>{info.reason}</Text>
    </Space>
  );
}

export default function SkillAgentConfigCard({
  capabilities,
  availability,
  disabledSkillNames,
  disabledAgentNames,
  onChange,
  onSave,
  isSaving,
  isLoading = false,
  error,
  onRetry,
  isCheckingAvailability = false,
  onCheckAvailability,
}: SkillAgentConfigCardProps) {
  const { cardStyle, sectionCardBodyStyle } = useStyles();
  const colors = useColors();
  const [view, setView] = useState<CapabilityView>("skills");
  const skillNames = capabilities?.skills.map((skill) => skill.name) ?? [];
  const agentNames = capabilities?.agents.map((agent) => agent.name) ?? [];
  const disabledSkills = new Set(disabledSkillNames);
  const disabledAgents = new Set(disabledAgentNames);

  return (
    <Card
      title={<span><BranchesOutlined style={{ marginRight: 8 }} />Skill 与 Agent</span>}
      style={{ ...cardStyle, marginBottom: 16 }}
      styles={{ body: sectionCardBodyStyle }}
    >
      <div style={{ marginBottom: 14, color: colors.textSecondary, lineHeight: 1.7 }}>
        控制当前账号可用的 Chat 路由能力。关闭 Skill 会同步限制关联工具；关闭 Agent 后将不再参与多维分析。
      </div>
      {capabilities && (
        <div style={{ marginBottom: 14 }}>
          <div style={{ marginBottom: 8, color: colors.textMuted, fontSize: 12 }}>能力预设</div>
          <Space size={[8, 8]} wrap>
            {CAPABILITY_PRESETS.map((preset) => (
              <Button
                key={preset.id}
                size="small"
                title={preset.description}
                onClick={() => onChange(applyCapabilityPreset(preset.id, skillNames, agentNames))}
              >
                {preset.label}
              </Button>
            ))}
          </Space>
        </div>
      )}
      {availability && (
        <div
          style={{
            display: "flex",
            alignItems: "center",
            justifyContent: "space-between",
            gap: 12,
            marginBottom: 14,
            padding: "10px 12px",
            border: `1px solid ${colors.border}`,
            borderRadius: 8,
            background: colors.nestedBg,
          }}
        >
          <AvailabilityStatus info={availability.llm} />
          {onCheckAvailability && (
            <Button size="small" loading={isCheckingAvailability} onClick={onCheckAvailability}>
              重新检测
            </Button>
          )}
        </div>
      )}
      <SectionDataState
        isLoading={isLoading}
        error={error}
        onRetry={onRetry}
        errorTitle="Skill 与 Agent 加载失败"
        isEmpty={!isLoading && !error && !capabilities}
        emptyText="暂无 Chat 能力数据"
        minHeight={180}
        skeletonRows={4}
      >
        {capabilities && (
          <>
            <Segmented
              value={view}
              onChange={(value) => setView(value as CapabilityView)}
              options={[
                { label: `Skill (${capabilities.skills.length})`, value: "skills", icon: <BranchesOutlined /> },
                { label: `Agent (${capabilities.agents.length})`, value: "agents", icon: <RobotOutlined /> },
              ]}
              style={{ marginBottom: 14 }}
            />

            <div style={{ display: "grid", gap: 10 }}>
              {view === "skills" && capabilities.skills.map((skill) => {
                const enabled = !disabledSkills.has(skill.name);
                return (
                  <div
                    key={skill.name}
                    style={{
                      display: "flex",
                      alignItems: "center",
                      justifyContent: "space-between",
                      gap: 16,
                      padding: "12px 14px",
                      border: `1px solid ${colors.border}`,
                      borderRadius: 10,
                      background: colors.nestedBg,
                    }}
                  >
                    <div style={{ minWidth: 0 }}>
                      <Space size={8} wrap>
                        <Text strong>{skill.description}</Text>
                        <Text code>{skill.name}</Text>
                        <Tag color="blue">P{skill.priority}</Tag>
                        <Tag>{skill.tool_names.length} Tools</Tag>
                      </Space>
                      <div style={{ marginTop: 5, color: colors.textMuted, fontSize: 12 }}>
                        {skill.triggers.join("；")}
                      </div>
                      <div style={{ marginTop: 6, color: colors.textMuted }}>
                        <AvailabilityStatus info={availability?.skills[skill.name]} />
                      </div>
                    </div>
                    <Switch
                      checked={enabled}
                      checkedChildren="启用"
                      unCheckedChildren="关闭"
                      aria-label={`${skill.description} Skill`}
                      onChange={(checked) => onChange({
                        disabled_chat_skills: updateDisabledNames(
                          skillNames,
                          disabledSkillNames,
                          skill.name,
                          checked,
                        ),
                      })}
                    />
                  </div>
                );
              })}

              {view === "agents" && capabilities.agents.map((agent) => {
                const enabled = !disabledAgents.has(agent.name);
                return (
                  <div
                    key={agent.name}
                    style={{
                      display: "flex",
                      alignItems: "center",
                      justifyContent: "space-between",
                      gap: 16,
                      padding: "12px 14px",
                      border: `1px solid ${colors.border}`,
                      borderRadius: 10,
                      background: colors.nestedBg,
                    }}
                  >
                    <div style={{ minWidth: 0 }}>
                      <Space size={8} wrap>
                        <Text strong>{agent.display_name}</Text>
                        <Text code>{agent.name}</Text>
                        <Tag color="purple">最多 {agent.max_rounds} 轮</Tag>
                        <Tag>{agent.tool_names.length} Tools</Tag>
                      </Space>
                      <div style={{ marginTop: 5, color: colors.textMuted, fontSize: 12 }}>
                        {agent.description}
                      </div>
                      <div style={{ marginTop: 6, color: colors.textMuted }}>
                        <AvailabilityStatus info={availability?.agents[agent.name]} />
                      </div>
                    </div>
                    <Switch
                      checked={enabled}
                      checkedChildren="启用"
                      unCheckedChildren="关闭"
                      aria-label={`${agent.display_name} Agent`}
                      onChange={(checked) => onChange({
                        disabled_chat_agents: updateDisabledNames(
                          agentNames,
                          disabledAgentNames,
                          agent.name,
                          checked,
                        ),
                      })}
                    />
                  </div>
                );
              })}
            </div>
          </>
        )}
      </SectionDataState>

      <Divider style={{ borderColor: colors.border, margin: "16px 0" }} />
      <Button
        type="primary"
        icon={<SaveOutlined />}
        onClick={onSave}
        loading={isSaving}
        disabled={!capabilities}
      >
        保存 Skill 与 Agent
      </Button>
    </Card>
  );
}
