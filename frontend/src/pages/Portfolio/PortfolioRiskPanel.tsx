import { Alert, Card, Col, Row, Space, Statistic, Tag, Typography } from "antd";
import type { PortfolioRiskSummary } from "../../types/portfolio";
import { useColors, useStyles, semanticTagStyle } from "../../styles/ui";
import type { SemanticTagColor } from "../../theme/hooks";

const { Text } = Typography;

interface PortfolioRiskPanelProps {
  risk: PortfolioRiskSummary;
}

const levelMeta: Record<PortfolioRiskSummary["concentration_level"], { color: SemanticTagColor; label: string }> = {
  low: { color: "down", label: "低风险" },
  medium: { color: "warning", label: "中风险" },
  high: { color: "up", label: "高风险" },
  unknown: { color: "info", label: "待评估" },
};

export default function PortfolioRiskPanel({ risk }: PortfolioRiskPanelProps) {
  const colors = useColors();
  const { cardStyle } = useStyles();
  const level = levelMeta[risk.concentration_level];
  const largestPosition = risk.largest_position_stock_name && risk.largest_position_stock_code
    ? `${risk.largest_position_stock_name} · ${risk.largest_position_stock_code}`
    : "暂无可评估持仓";

  return (
    <Card
      size="small"
      title="持仓集中度"
      extra={<Tag style={semanticTagStyle(level.color)}>{level.label}</Tag>}
      style={{ ...cardStyle, marginBottom: 16 }}
    >
      <Row gutter={[16, 12]}>
        <Col xs={24} md={8}>
          <Statistic
            title="最大单股权重"
            value={risk.max_single_stock_pct ?? "-"}
            precision={2}
            suffix={risk.max_single_stock_pct == null ? undefined : "%"}
          />
          <Text style={{ color: colors.textMuted, fontSize: 12 }}>{largestPosition}</Text>
        </Col>
        <Col xs={12} md={8}>
          <Statistic
            title="前三大持仓占比"
            value={risk.top3_concentration_pct ?? "-"}
            precision={2}
            suffix={risk.top3_concentration_pct == null ? undefined : "%"}
          />
        </Col>
        <Col xs={12} md={8}>
          <Statistic title="已定价股票" value={risk.priced_stock_count} suffix="只" />
          {risk.unpriced_stock_count > 0 ? (
            <Text style={{ color: colors.textMuted, fontSize: 12 }}>
              另有 {risk.unpriced_stock_count} 只缺少行情
            </Text>
          ) : null}
        </Col>
      </Row>

      {risk.warnings?.length ? (
        <Alert
          type={risk.concentration_level === "high" ? "warning" : "info"}
          showIcon
          title="风险提示"
          description={(
            <Space orientation="vertical" size={2}>
              {risk.warnings.map((warning) => <Text key={warning}>{warning}</Text>)}
            </Space>
          )}
          style={{ marginTop: 16 }}
        />
      ) : null}
    </Card>
  );
}
