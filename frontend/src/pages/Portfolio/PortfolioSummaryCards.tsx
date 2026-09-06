import { Alert, Card, Col, Row, Statistic, Typography } from "antd";
import {
  CheckCircleOutlined,
  FundOutlined,
  LineChartOutlined,
  RiseOutlined,
  StockOutlined,
  WalletOutlined,
} from "@ant-design/icons";
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
        <Col xs={12} lg={8} xl={4}>
          <Card
            size="small"
            style={{
              ...cardStyle,
              position: "relative",
              overflow: "hidden",
              borderLeft: `3px solid var(--c-primary)`,
            }}
            className="u-card-interactive"
          >
            <Statistic
              title={<span><WalletOutlined style={{ marginRight: 6 }} />最新市值</span>}
              value={summary.total_market_value}
              precision={2}
              prefix="¥"
              styles={{ content: { fontFamily: "var(--c-font-mono)", fontWeight: 700 } }}
            />
            <Text style={{ color: colors.textMuted, fontSize: "var(--c-font-sm)" }}>
              已定价成本 {formatMoney(summary.priced_cost)}
            </Text>
          </Card>
        </Col>
        <Col xs={12} lg={8} xl={4}>
          <Card
            size="small"
            style={{
              ...cardStyle,
              position: "relative",
              overflow: "hidden",
              borderLeft: `3px solid ${changeColor(summary.combined_profit_amount, colors)}`,
            }}
            className="u-card-interactive"
          >
            <Statistic
              title={<span><FundOutlined style={{ marginRight: 6 }} />综合盈亏</span>}
              value={summary.combined_profit_amount}
              precision={2}
              prefix="¥"
              styles={{
                content: {
                  fontFamily: "var(--c-font-mono)",
                  fontWeight: 700,
                  color: changeColor(summary.combined_profit_amount, colors),
                },
              }}
            />
            <Text style={{ color: colors.textMuted, fontSize: "var(--c-font-sm)" }}>
              共 {summary.transaction_count} 笔交易流水
            </Text>
          </Card>
        </Col>
        <Col xs={12} lg={8} xl={4}>
          <Card
            size="small"
            style={{
              ...cardStyle,
              position: "relative",
              overflow: "hidden",
              borderLeft: `3px solid ${changeColor(summary.unrealized_profit_amount, colors)}`,
            }}
            className="u-card-interactive"
          >
            <Statistic
              title={<span><RiseOutlined style={{ marginRight: 6 }} />浮动盈亏</span>}
              value={summary.unrealized_profit_amount}
              precision={2}
              prefix="¥"
              styles={{
                content: {
                  fontFamily: "var(--c-font-mono)",
                  fontWeight: 700,
                  color: changeColor(summary.unrealized_profit_amount, colors),
                },
              }}
            />
            <Text style={{ color: colors.textMuted, fontSize: "var(--c-font-sm)" }}>
              盈利 {summary.profitable_count} · 亏损 {summary.losing_count}
            </Text>
          </Card>
        </Col>
        <Col xs={12} lg={8} xl={4}>
          <Card
            size="small"
            style={{
              ...cardStyle,
              position: "relative",
              overflow: "hidden",
              borderLeft: `3px solid ${changeColor(summary.total_profit_pct, colors)}`,
            }}
            className="u-card-interactive"
          >
            <Statistic
              title={<span><LineChartOutlined style={{ marginRight: 6 }} />浮动收益率</span>}
              value={summary.total_profit_pct ?? "-"}
              precision={2}
              suffix={summary.total_profit_pct == null ? undefined : "%"}
              styles={{
                content: {
                  fontFamily: "var(--c-font-mono)",
                  fontWeight: 700,
                  color: changeColor(summary.total_profit_pct, colors),
                },
              }}
            />
            <Text style={{ color: colors.textMuted, fontSize: "var(--c-font-sm)" }}>
              基于已定价持仓计算
            </Text>
          </Card>
        </Col>
        <Col xs={12} lg={8} xl={4}>
          <Card
            size="small"
            style={{
              ...cardStyle,
              position: "relative",
              overflow: "hidden",
              borderLeft: `3px solid #1890ff`,
            }}
            className="u-card-interactive"
          >
            <Statistic
              title={<span><StockOutlined style={{ marginRight: 6 }} />持仓总成本</span>}
              value={summary.total_cost}
              precision={2}
              prefix="¥"
              styles={{ content: { fontFamily: "var(--c-font-mono)", fontWeight: 700 } }}
            />
            <Text style={{ color: colors.textMuted, fontSize: "var(--c-font-sm)" }}>
              {summary.stock_count} 只股票 · {summary.position_count} 个剩余批次
            </Text>
          </Card>
        </Col>
        <Col xs={12} lg={8} xl={4}>
          <Card
            size="small"
            style={{
              ...cardStyle,
              position: "relative",
              overflow: "hidden",
              borderLeft: `3px solid ${changeColor(summary.realized_profit_amount, colors)}`,
            }}
            className="u-card-interactive"
          >
            <Statistic
              title={<span><CheckCircleOutlined style={{ marginRight: 6 }} />已实现盈亏</span>}
              value={summary.realized_profit_amount}
              precision={2}
              prefix="¥"
              styles={{
                content: {
                  fontFamily: "var(--c-font-mono)",
                  fontWeight: 700,
                  color: changeColor(summary.realized_profit_amount, colors),
                },
              }}
            />
            <Text style={{ color: colors.textMuted, fontSize: "var(--c-font-sm)" }}>按 FIFO 成本核算卖出</Text>
          </Card>
        </Col>
      </Row>
    </>
  );
}
