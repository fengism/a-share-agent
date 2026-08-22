import { BranchesOutlined } from "@ant-design/icons";
import { Segmented, Select, Space, Tag, Typography } from "antd";
import { semanticTagStyle } from "../../../styles/ui";
import type {
  ChatCapabilityAvailabilityResponse,
  SkillCapabilityInfo,
} from "../../../types/capabilities";

const { Text } = Typography;

interface ChatSkillSelectorProps {
  skills: SkillCapabilityInfo[];
  disabledSkillNames: string[];
  availability?: ChatCapabilityAvailabilityResponse;
  skillNames: string[] | null;
  onChange: (skillNames: string[] | null) => void;
  disabled: boolean;
}

export function ChatSkillSelector({
  skills,
  disabledSkillNames,
  availability,
  skillNames,
  onChange,
  disabled,
}: ChatSkillSelectorProps) {
  const disabledNames = new Set(disabledSkillNames);
  const selectableSkills = skills.filter((skill) => {
    const status = availability?.skills[skill.name]?.status;
    return !disabledNames.has(skill.name) && status !== "unavailable" && status !== "disabled";
  });
  const selectableNames = new Set(selectableSkills.map((skill) => skill.name));
  const selectedNames = (skillNames ?? []).filter((name) => selectableNames.has(name));
  const usesAccountDefaults = skillNames === null;

  return (
    <div className="chat-skill-selector">
      <div className="chat-skill-selector-heading">
        <Space size={8}>
          <BranchesOutlined />
          <Text strong>本会话 Skill</Text>
        </Space>
        <Segmented
          size="small"
          value={usesAccountDefaults ? "default" : "custom"}
          disabled={disabled}
          options={[
            { label: "账号默认", value: "default" },
            { label: "自选 Skill", value: "custom" },
          ]}
          onChange={(value) => {
            if (value === "default") onChange(null);
            else onChange(selectableSkills.map((skill) => skill.name));
          }}
        />
      </div>

      {!usesAccountDefaults && (
        <Select
          mode="multiple"
          allowClear
          value={selectedNames}
          disabled={disabled}
          placeholder="留空则不调用 Skill 工具"
          options={selectableSkills.map((skill) => ({
            value: skill.name,
            label: skill.description,
          }))}
          onChange={onChange}
          style={{ width: "100%" }}
        />
      )}

      <div className="chat-skill-selector-status">
        {selectableSkills.map((skill) => {
          const info = availability?.skills[skill.name];
          return (
            <span key={skill.name}>
              <Tag style={semanticTagStyle(info?.status === "degraded" ? "warning" : "info")}>
                {skill.description}
              </Tag>
              {info?.status === "degraded" && <Text type="secondary">{info.reason}</Text>}
            </span>
          );
        })}
        {selectableSkills.length === 0 && <Text type="secondary">当前账号没有可用 Skill</Text>}
      </div>
    </div>
  );
}
