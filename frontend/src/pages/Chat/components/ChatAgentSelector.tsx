import { RobotOutlined } from "@ant-design/icons";
import { Segmented, Select, Space, Tag, Typography } from "antd";
import type {
  AgentCapabilityInfo,
  ChatCapabilityAvailabilityResponse,
} from "../../../types/capabilities";

const { Text } = Typography;

interface ChatAgentSelectorProps {
  agents: AgentCapabilityInfo[];
  disabledAgentNames: string[];
  availability?: ChatCapabilityAvailabilityResponse;
  agentNames: string[] | null;
  onChange: (agentNames: string[] | null) => void;
  disabled: boolean;
}

export function ChatAgentSelector({
  agents,
  disabledAgentNames,
  availability,
  agentNames,
  onChange,
  disabled,
}: ChatAgentSelectorProps) {
  const disabledNames = new Set(disabledAgentNames);
  const selectableAgents = agents.filter((agent) => {
    const status = availability?.agents[agent.name]?.status;
    return !disabledNames.has(agent.name) && status !== "unavailable" && status !== "disabled";
  });
  const selectableNames = new Set(selectableAgents.map((agent) => agent.name));
  const selectedNames = (agentNames ?? []).filter((name) => selectableNames.has(name));
  const isAutomatic = agentNames === null;

  return (
    <div className="chat-agent-selector">
      <div className="chat-agent-selector-heading">
        <Space size={8}>
          <RobotOutlined />
          <Text strong>本会话 Agent</Text>
        </Space>
        <Segmented
          size="small"
          value={isAutomatic ? "automatic" : "custom"}
          disabled={disabled}
          options={[
            { label: "自动路由", value: "automatic" },
            { label: "自选 Agent", value: "custom" },
          ]}
          onChange={(value) => {
            if (value === "automatic") onChange(null);
            else onChange(selectableAgents.map((agent) => agent.name));
          }}
        />
      </div>

      {!isAutomatic && (
        <Select
          mode="multiple"
          allowClear
          value={selectedNames}
          disabled={disabled}
          placeholder="留空则使用单 Agent"
          options={selectableAgents.map((agent) => ({
            value: agent.name,
            label: agent.display_name,
          }))}
          onChange={onChange}
          style={{ width: "100%" }}
        />
      )}

      <div className="chat-agent-selector-status">
        {selectableAgents.map((agent) => {
          const info = availability?.agents[agent.name];
          return (
            <span key={agent.name}>
              <Tag color={info?.status === "degraded" ? "gold" : "blue"}>
                {agent.display_name}
              </Tag>
              {info?.status === "degraded" && <Text type="secondary">{info.reason}</Text>}
            </span>
          );
        })}
        {selectableAgents.length === 0 && <Text type="secondary">当前账号没有可用专业 Agent</Text>}
      </div>
    </div>
  );
}
