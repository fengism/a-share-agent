import { Alert, Card, Col, Row, Statistic, Typography } from "antd";
import { useColors, useStyles } from "../../styles/ui";
import type { PortfolioSummary } from "../../types/portfolio";
import { changeColor } from "../../utils/format";
import { formatMoney } from "./portfolioFormatters";

const { Text } = Typography;

interface PortfolioSummaryCardsProps {
  summary: PortfolioSummary;
}

export default function PortfolioSummaryCards({ summary }: PortfolioSummaryCardsProps) {
  const colors = useColors();
  const { cardStyle } = useStyles();

  return (
    <>
      {summary.unpriced_count > 0 ? (
        <Alert
          type="warning"
          showIcon
          title={`${summary.unpriced_count} 只股票暂未获取到行情`}
          description="最新市值和浮动盈亏仅汇总已成功定价的持仓。"
          style={{ marginBottom: 16 }}
        />
      ) : null}

      <Row gutter={[12, 12]} style={{ marginBottom: 16 }}>
        <Col xs={12} lg={6}>
          <Card size="small" style={cardStyle}>
            <Statistic title="持仓总成本" value={summary.total_cost} precision={2} prefix="¥" />
            <Text style={{ color: colors.textMuted, fontSize: 12 }}>
              {summary.stock_count} 只股票 · {summary.position_count} 笔买入
            </Text>
          </Card>
        </Col>
        <Col xs={12} lg={6}>
          <Card size="small" style={cardStyle}>
            <Statistic title="最新市值" value={summary.total_market_value} precision={2} prefix="¥" />
            <Text style={{ color: colors.textMuted, fontSize: 12 }}>
              已定价成本 {formatMoney(summary.priced_cost)}
            </Text>
          </Card>
        </Col>
        <Col xs={12} lg={6}>
          <Card size="small" style={cardStyle}>
            <Statistic
              title="浮动盈亏"
              value={summary.total_profit_amount}
              precision={2}
              prefix="¥"
              valueStyle={{ color: changeColor(summary.total_profit_amount, colors) }}
            />
            <Text style={{ color: colors.textMuted, fontSize: 12 }}>
              盈利 {summary.profitable_count} · 亏损 {summary.losing_count}
            </Text>
          </Card>
        </Col>
        <Col xs={12} lg={6}>
          <Card size="small" style={cardStyle}>
            <Statistic
              title="总收益率"
              value={summary.total_profit_pct ?? "-"}
              precision={2}
              suffix={summary.total_profit_pct == null ? undefined : "%"}
              valueStyle={{ color: changeColor(summary.total_profit_pct, colors) }}
            />
            <Text style={{ color: colors.textMuted, fontSize: 12 }}>
              基于已定价持仓计算
            </Text>
          </Card>
        </Col>
      </Row>
    </>
  );
}
