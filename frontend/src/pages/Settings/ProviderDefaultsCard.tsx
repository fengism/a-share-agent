import { Card, Typography } from "antd";
import { useColors, useStyles } from "../../styles/ui";
import type { LlmApiMode, ProviderDefault } from "../../types/settings";

const { Text } = Typography;

const API_MODE_LABELS: Record<LlmApiMode, string> = {
  auto: "自动（跟随 Provider）",
  openai: "OpenAI Compatible",
  litellm: "LiteLLM",
};

export function ProviderDefaultsCard({ providerDefaults }: { providerDefaults: Record<string, ProviderDefault> }) {
  const { cardStyle, sectionCardBodyStyle } = useStyles();
  const colors = useColors();

  return (
    <Card title="Provider 默认值参考" style={cardStyle} styles={{ body: sectionCardBodyStyle }}>
      <div style={{ display: "grid", gridTemplateColumns: "repeat(auto-fill, minmax(280px, 1fr))", gap: 12 }}>
        {Object.entries(providerDefaults).map(([name, defaults]) => (
          <div
            key={name}
            style={{
              padding: "var(--c-pad-inset, 7px 12px)",
              background: colors.hoverBg,
              border: `1px solid ${colors.border}`,
              borderRadius: 8,
              fontSize: "var(--c-font-sm)",
            }}
          >
            <Text strong style={{ color: colors.primary, fontSize: "var(--c-font-md)" }}>
              {defaults.label || name}
            </Text>
            <div style={{ marginTop: 4, color: colors.textMuted }}>{defaults.description}</div>
            <div style={{ marginTop: 6, color: colors.textSecondary, wordBreak: "break-all" }}>
              <div>模式: {API_MODE_LABELS[defaults.api_mode]}</div>
              <div>API Key: {defaults.api_key_required ? "必填" : "可选"}</div>
              <div>URL: {defaults.base_url}</div>
              <div>Model: {defaults.model}</div>
              {defaults.api_version && <div>API Version: {defaults.api_version}</div>}
            </div>
          </div>
        ))}
      </div>
    </Card>
  );
}
