import { LinkOutlined } from "@ant-design/icons";
import { Typography } from "antd";
import type { AgentToolResultSummary as ToolSummary } from "../../types/chat";

const { Text } = Typography;

const METADATA_LABELS: Record<string, string> = {
  analysis_date: "分析日期",
  code: "代码",
  date: "日期",
  name: "名称",
  period: "周期",
  report_date: "报告期",
  source: "数据源",
};

export default function ToolResultSummary({ value }: { value?: ToolSummary }) {
  if (!value) return null;
  const metadata = Object.entries(value.metadata ?? {});
  const sources = value.sources ?? [];

  return (
    <div
      data-testid="tool-result-summary"
      style={{
        marginTop: "var(--c-space-2)",
        color: "var(--c-text-secondary)",
        fontSize: "var(--c-font-sm)",
        lineHeight: "var(--c-leading-relaxed)",
      }}
    >
      <Text type="secondary" style={{ fontSize: "inherit", lineHeight: "inherit", fontWeight: "var(--c-weight-semibold)" }}>
        结果摘要
      </Text>
      <div style={{ marginTop: "var(--c-space-1)", fontSize: "inherit", lineHeight: "inherit" }}>
        {value.summary}
      </div>
      {metadata.length > 0 ? (
        <div style={{ display: "flex", flexWrap: "wrap", gap: "var(--c-space-2)", marginTop: "var(--c-space-1)", fontSize: "inherit", lineHeight: "inherit" }}>
          {metadata.map(([key, item]) => (
            <span key={key}>{METADATA_LABELS[key] || key}：{item}</span>
          ))}
        </div>
      ) : null}
      {sources.length > 0 ? (
        <div style={{ display: "grid", gap: "var(--c-space-1)", marginTop: "var(--c-space-2)" }}>
          {sources.map((source) => (
            <a
              key={source.url}
              href={source.url}
              target="_blank"
              rel="noreferrer"
              style={{ overflowWrap: "anywhere", fontSize: "inherit", lineHeight: "inherit" }}
            >
              <LinkOutlined /> {source.title || source.domain || source.url}
            </a>
          ))}
        </div>
      ) : null}
    </div>
  );
}
