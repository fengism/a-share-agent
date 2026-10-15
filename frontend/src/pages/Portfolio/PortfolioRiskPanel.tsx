import { Alert, Card, Col, Row, Space, Statistic, Tag, Typography } from "antd";
import type { PortfolioRiskSummary } from "../../types/portfolio";
import { useColors, useStyles, semanticTagStyle } from "../../styles/ui";
import type { SemanticTagColor } from "../../theme/hooks";
import { formatMoney } from "./portfolioFormatters";

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
  const largestSector = risk.largest_sector_name ?? "暂无行业归属";

  return (
    <Card
      size="small"
      title="仓位风险"
      extra={<Tag style={semanticTagStyle(level.color)}>{level.label}</Tag>}
      style={{ ...cardStyle, marginBottom: 16 }}
    >
      <Row gutter={[16, 12]}>
        <Col xs={12} md={6}>
          <Statistic
            className="portfolio-risk-stat"
            title="总仓位上限"
            value={risk.max_total_position_limit_pct}
            precision={2}
            suffix="%"
          />
          <Text className="portfolio-risk-subtext" style={{ color: colors.textMuted, fontSize: "var(--c-font-sm)" }}>
            买入预演超过上限时提示
          </Text>
        </Col>
        <Col xs={12} md={6}>
          <Statistic
            className="portfolio-risk-stat"
            title="最大单股权重"
            value={risk.max_single_stock_pct ?? "-"}
            precision={2}
            suffix={risk.max_single_stock_pct == null ? undefined : "%"}
          />
          <Text className="portfolio-risk-subtext" style={{ color: colors.textMuted, fontSize: "var(--c-font-sm)", display: "block" }}>
            {largestPosition}
          </Text>
          <Text className="portfolio-risk-subtext" style={{ color: colors.textMuted, fontSize: "var(--c-font-sm)" }}>
            上限 {risk.max_single_stock_limit_pct.toFixed(2)}%
          </Text>
        </Col>
        <Col xs={12} md={6}>
          <Statistic
            className="portfolio-risk-stat"
            title="最大行业仓位"
            value={risk.largest_sector_pct ?? "-"}
            precision={2}
            suffix={risk.largest_sector_pct == null ? undefined : "%"}
          />
          <Text className="portfolio-risk-subtext" style={{ color: colors.textMuted, fontSize: "var(--c-font-sm)", display: "block" }}>
            {largestSector}
          </Text>
          <Text className="portfolio-risk-subtext" style={{ color: colors.textMuted, fontSize: "var(--c-font-sm)" }}>
            上限 {risk.max_sector_limit_pct.toFixed(2)}%
          </Text>
        </Col>
        <Col xs={12} md={6}>
          <Statistic
            className="portfolio-risk-stat"
            title="前三大持仓占比"
            value={risk.top3_concentration_pct ?? "-"}
            precision={2}
            suffix={risk.top3_concentration_pct == null ? undefined : "%"}
          />
          <Text className="portfolio-risk-subtext" style={{ color: colors.textMuted, fontSize: "var(--c-font-sm)" }}>
            已定价 {risk.priced_stock_count} 只
            {risk.unpriced_stock_count > 0 ? ` · 未定价 ${risk.unpriced_stock_count} 只` : ""}
          </Text>
        </Col>
      </Row>

      {risk.sector_allocations?.length ? (
        <div style={{ marginTop: 16 }}>
          <Text strong style={{ display: "block", marginBottom: 8 }}>行业仓位</Text>
          <Space wrap size={[8, 8]}>
            {risk.sector_allocations.map((sector) => (
              <Tag key={sector.sector_name}>
                {sector.sector_name} {sector.allocation_pct == null ? "-" : `${sector.allocation_pct.toFixed(2)}%`}
                <Text style={{ color: colors.textMuted, marginLeft: 6 }}>
                  {formatMoney(sector.market_value)} · {sector.stock_codes?.length ?? 0} 只
                </Text>
              </Tag>
            ))}
          </Space>
        </div>
      ) : null}

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
