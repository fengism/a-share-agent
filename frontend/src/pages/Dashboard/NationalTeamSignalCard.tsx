import { ArrowRightOutlined } from "@ant-design/icons";
import { Card, Tag, Tooltip, Typography } from "antd";
import { useNationalTeamOverview } from "../../api/queries";
import PreloadLink from "../../components/PreloadLink";
import { useColors } from "../../styles/ui";
import { buildSparklinePath } from "../../utils/sparkline";

const { Text } = Typography;

const STATUS_COLORS = {
  strong: { text: "#f5222d", tag: "red" },
  active: { text: "#fa8c16", tag: "orange" },
  moderate: { text: "#1677ff", tag: "blue" },
  neutral: { text: "#64748b", tag: "default" },
} as const;

function formatFlow(value: number | null | undefined) {
  if (value == null) return "—";
  return `${value >= 0 ? "+" : ""}${value.toFixed(1)} 亿`;
}

export default function NationalTeamSignalCard() {
  const colors = useColors();
  const { data, isLoading } = useNationalTeamOverview(120);

  if (isLoading && !data) {
    return <Card size="small" loading data-testid="dashboard-national-team-signal" />;
  }
  if (!data) return null;

  const support = data.support_score;
  if (!support) return null;
  const summary = data.summary;
  const history = data.support_score_history ?? [];
  const score = support.score;
  const confidence = Math.round((support.confidence ?? 0) * 100);
  const status = STATUS_COLORS[support.status] ?? STATUS_COLORS.neutral;
  const sparkline = buildSparklinePath(
    history.map((point) => point.score),
    132,
    26,
  );
  const freshness = data.stale
    ? "份额停留在上一交易日"
    : data.partial
      ? "部分 ETF 数据缺失"
      : "数据完整";
  const confidenceHint =
    confidence >= 80
      ? "ETF 覆盖率与数据新鲜度良好。"
      : confidence >= 50
        ? "部分 ETF 份额或行情缺失，结论仅供参考。"
        : "样本覆盖不足或数据陈旧，请勿据此单独决策。";

  return (
    <Card
      size="small"
      data-testid="dashboard-national-team-signal"
      styles={{ body: { padding: "10px 14px" } }}
    >
      <div style={{ display: "flex", alignItems: "center", gap: 12, flexWrap: "wrap" }}>
        <div
          aria-hidden
          style={{
            display: "flex",
            flexDirection: "column",
            alignItems: "center",
            justifyContent: "center",
            width: 48,
            height: 48,
            borderRadius: "50%",
            border: `2px solid ${status.text}`,
            color: status.text,
            flexShrink: 0,
          }}
        >
          <span style={{ fontSize: 18, fontWeight: 700, lineHeight: 1 }}>{Math.round(score)}</span>
          <span style={{ fontSize: 9, color: colors.textSecondary, marginTop: 2 }}>强度</span>
        </div>

        <div style={{ flex: 1, minWidth: 200 }}>
          <div style={{ display: "flex", alignItems: "center", gap: 6, flexWrap: "wrap" }}>
            <Text strong style={{ fontSize: 13 }}>
              国家队托底信号
            </Text>
            <Tag color={status.tag} style={{ margin: 0, fontSize: 10, lineHeight: "16px" }}>
              {support.label}
            </Tag>
            <Tooltip title={confidenceHint}>
              <Tag
                color={confidence >= 80 ? "green" : confidence >= 50 ? "gold" : "red"}
                style={{ margin: 0, fontSize: 10, lineHeight: "16px" }}
                data-testid="dashboard-national-team-confidence"
              >
                置信度 {confidence}%
              </Tag>
            </Tooltip>
          </div>
          <Text type="secondary" style={{ display: "block", fontSize: 11, marginTop: 3 }}>
            1 日净申购 {formatFlow(summary?.estimated_net_flow_1d_100m)} · 5 日{" "}
            {formatFlow(summary?.estimated_net_flow_5d_100m)} · 覆盖{" "}
            {data.covered_etf_count}/{data.total_etf_count} 只 ETF · {freshness}
          </Text>
          {data.as_of_date ? (
            <Text type="secondary" style={{ display: "block", fontSize: 10, marginTop: 2 }}>
              数据截至 {data.as_of_date}
              {data.partial ? " · 结果可能随后续刷新变化" : ""}
            </Text>
          ) : null}
        </div>

        {sparkline ? (
          <div style={{ display: "flex", alignItems: "center", gap: 6, flexShrink: 0 }}>
            <svg
              width={sparkline.width}
              height={sparkline.height}
              viewBox={`0 0 ${sparkline.width} ${sparkline.height}`}
              role="img"
              aria-label={`近 ${sparkline.count} 个交易日托底评分走势`}
            >
              <path
                d={sparkline.path}
                fill="none"
                stroke={sparkline.delta >= 0 ? "#f5222d" : "#00b96b"}
                strokeWidth={1.5}
                strokeLinejoin="round"
                strokeLinecap="round"
              />
            </svg>
            <Text type="secondary" style={{ fontSize: 10, fontFamily: "var(--c-font-mono)" }}>
              {sparkline.delta >= 0 ? "+" : ""}
              {sparkline.delta.toFixed(1)}
            </Text>
          </div>
        ) : null}

        <PreloadLink
          to="/national-team"
          style={{ fontSize: 12, whiteSpace: "nowrap", color: colors.primary }}
          aria-label="查看国家队监测详情"
        >
          查看详情 <ArrowRightOutlined />
        </PreloadLink>
      </div>
    </Card>
  );
}
