import {
  CompassOutlined,
  FileTextOutlined,
  FilterOutlined,
  FundOutlined,
  RobotOutlined,
} from "@ant-design/icons";
import { Button, Typography } from "antd";
import { useColors, useTokens } from "../../../styles/ui";
import { SAMPLE_PROMPTS } from "../constants";

const { Text, Title } = Typography;

interface EmptyChatStateProps {
  onSelectPrompt: (prompt: string) => void;
}

const CATEGORIZED_PROMPTS = [
  { icon: <FundOutlined />, title: "个股分析", prompt: "贵州茅台怎么样，分析估值与机构一致预期" },
  { icon: <FilterOutlined />, title: "策略选股", prompt: "帮我找PE小于20且股息率大于3%的优质白马股" },
  { icon: <CompassOutlined />, title: "盘面主线", prompt: "今日大盘主线题材与涨停连板龙头有哪些？" },
  { icon: <FileTextOutlined />, title: "舆情研报", prompt: "帮我总结近期半导体芯片产业链的最新研报与核心看点" },
];

export function EmptyChatState({ onSelectPrompt }: EmptyChatStateProps) {
  const c = useColors();
  const t = useTokens();

  return (
    <div
      style={{
        textAlign: "center",
        color: c.textMuted,
        padding: `${t.space[6]} ${t.space[4]}`,
        maxWidth: 720,
        margin: "0 auto",
      }}
    >
      <div
        style={{
          width: 56,
          height: 56,
          borderRadius: t.radius.xl,
          background: `linear-gradient(135deg, ${c.primary}22, ${c.accent}33)`,
          border: `1px solid ${c.primary}44`,
          display: "grid",
          placeItems: "center",
          margin: "0 auto var(--c-space-3)",
          color: c.primary,
          fontSize: 28,
        }}
      >
        <RobotOutlined />
      </div>

      <Title level={4} style={{ color: c.textPrimary, margin: "0 0 var(--c-space-1)" }}>
        AI 选股与投研助手
      </Title>
      <Text type="secondary" style={{ display: "block", marginBottom: t.space[5], fontSize: t.font.sm }}>
        支持自然语言对话、财务三张表分析、多维度条件选股与实时行情问答
      </Text>

      <div
        style={{
          display: "grid",
          gridTemplateColumns: "repeat(auto-fit, minmax(280px, 1fr))",
          gap: t.space[3],
          textAlign: "left",
          marginBottom: t.space[4],
        }}
      >
        {CATEGORIZED_PROMPTS.map((item) => (
          <div
            key={item.title}
            role="button"
            tabIndex={0}
            onClick={() => onSelectPrompt(item.prompt)}
            onKeyDown={(e) => {
              if (e.key === "Enter" || e.key === " ") {
                e.preventDefault();
                onSelectPrompt(item.prompt);
              }
            }}
            className="u-card-interactive"
            style={{
              padding: `${t.space[3]} ${t.space[4]}`,
              borderRadius: t.radius.lg,
              border: `1px solid ${c.border}`,
              background: c.hoverBg,
              cursor: "pointer",
            }}
          >
            <div style={{ display: "flex", alignItems: "center", gap: t.space[2], marginBottom: 4 }}>
              <span style={{ color: c.primary }}>{item.icon}</span>
              <strong style={{ color: c.textPrimary, fontSize: t.font.sm }}>{item.title}</strong>
            </div>
            <div
              style={{
                color: c.textSecondary,
                fontSize: t.font.xs,
                lineHeight: 1.4,
                overflow: "hidden",
                textOverflow: "ellipsis",
                whiteSpace: "nowrap",
              }}
            >
              {item.prompt}
            </div>
          </div>
        ))}
      </div>

      <div
        style={{
          display: "flex",
          gap: t.space[2],
          justifyContent: "center",
          flexWrap: "wrap",
          alignItems: "center",
        }}
      >
        <span style={{ fontSize: t.font.xs, color: c.textMuted }}>更多示例：</span>
        {SAMPLE_PROMPTS.map((prompt) => (
          <Button
            key={prompt}
            type="text"
            size="small"
            style={{
              background: c.hoverBg,
              border: `1px solid ${c.border}`,
              color: c.textSecondary,
              borderRadius: t.radius.pill,
              fontSize: t.font.xs,
            }}
            onClick={() => onSelectPrompt(prompt)}
          >
            {prompt}
          </Button>
        ))}
      </div>
    </div>
  );
}
