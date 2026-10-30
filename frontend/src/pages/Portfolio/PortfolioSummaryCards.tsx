import { useState } from "react";
import { Alert, Button, Card, Col, Row, Statistic, Typography } from "antd";
import {
  BankOutlined,
  CheckCircleOutlined,
  EyeInvisibleOutlined,
  EyeOutlined,
  FundOutlined,
  LineChartOutlined,
  PieChartOutlined,
  RiseOutlined,
  SettingOutlined,
  StockOutlined,
  ThunderboltOutlined,
  WalletOutlined,
} from "@ant-design/icons";
import { useColors, useStyles } from "../../styles/ui";
import type { PortfolioStockSummary, PortfolioSummary } from "../../types/portfolio";
import { changeColor } from "../../utils/format";
import { formatMoney } from "./portfolioFormatters";

const { Text } = Typography;

const HOLDING_PALETTE = ["#1677ff", "#13c2c2", "#fa8c16", "#722ed1", "#eb2f96"];

interface PortfolioSummaryCardsProps {
  summary: PortfolioSummary;
  stocks?: PortfolioStockSummary[];
  onOpenSettings?: () => void;
}

export default function PortfolioSummaryCards({ summary, stocks, onOpenSettings }: PortfolioSummaryCardsProps) {
  const [masked, setMasked] = useState(false);
  const colors = useColors();
  const { cardStyle } = useStyles();
  const hasDailyProfit = summary.previous_close_value > 0;
  const positionPct = summary.total_position_pct ?? 0;
  const cashPct = Math.max(0, 100 - positionPct);

  return (
    <>
      {!summary.cash_configured ? (
        <Alert
          type="info"
          showIcon
          title="尚未配置初始资金"
          description="配置后可计算现金余额、总资产和真实仓位；当前仍按证券持仓内部市值展示集中度。"
          action={
            onOpenSettings ? (
              <Button size="small" type="primary" icon={<SettingOutlined />} onClick={onOpenSettings}>
                配置初始资金
              </Button>
            ) : null
          }
          style={{ marginBottom: 16 }}
        />
      ) : null}

      {summary.fx_rates?.HKD != null ? (
        <Alert
          type="info"
          showIcon
          title="港股金额已折算为人民币"
          description={`当前折算汇率：1 HKD = ${summary.fx_rates.HKD} CNY。行情和成交价仍按港币展示，汇总市值、成本、盈亏和现金均以人民币计。`}
          style={{ marginBottom: 16 }}
        />
      ) : null}

      {summary.unpriced_count > 0 ? (
        <Alert
          type="warning"
          showIcon
          title={`${summary.unpriced_count} 只股票暂未获取到行情`}
          description={summary.cash_configured
            ? "最新市值和浮动盈亏仅汇总已定价持仓；总资产与仓位已按未定价持仓的剩余成本估算。"
            : "最新市值和浮动盈亏仅汇总已成功定价的持仓。"}
          style={{ marginBottom: 16 }}
        />
      ) : null}

      <Row gutter={[12, 12]} style={{ marginBottom: 16 }} align="stretch">
        {/* 左侧：主资产与盈亏核心看板 */}
        <Col xs={24} lg={14} xl={14}>
          <Card
            size="small"
            style={{
              ...cardStyle,
              height: "100%",
              display: "flex",
              flexDirection: "column",
              justifyContent: "space-between",
              borderTop: "3px solid var(--c-primary)",
            }}
            className="portfolio-hero-card"
          >
            <div>
              <div style={{ display: "flex", justifyContent: "space-between", alignItems: "flex-start", marginBottom: 8 }}>
                <div>
                  <Statistic
                    className="portfolio-summary-stat portfolio-hero-stat"
                    title={
                      <span style={{ display: "inline-flex", alignItems: "center", gap: 6 }}>
                        <BankOutlined />
                        <span>总资产</span>
                        <Button
                          type="text"
                          size="small"
                          icon={masked ? <EyeInvisibleOutlined /> : <EyeOutlined />}
                          onClick={() => setMasked(!masked)}
                          style={{ padding: 0, height: 18, width: 18, color: colors.textMuted }}
                          title={masked ? "显示金额" : "隐藏金额"}
                        />
                      </span>
                    }
                    value={masked ? "••••••" : (summary.total_asset_value ?? "-")}
                    precision={masked ? undefined : 2}
                    prefix={masked || summary.total_asset_value == null ? undefined : "¥"}
                    styles={{
                      content: {
                        fontFamily: "var(--c-font-mono)",
                        fontWeight: 800,
                        fontSize: "calc(var(--c-font-lg, 18px) * 1.5)",
                        letterSpacing: "-0.02em",
                      },
                    }}
                  />
                  <Text className="portfolio-summary-subtext" style={{ color: colors.textMuted, fontSize: "var(--c-font-sm)" }}>
                    证券估值 {masked ? "••••••" : formatMoney(summary.estimated_securities_value)}
                  </Text>
                </div>

                {summary.cash_configured && summary.total_position_pct != null ? (
                  <div style={{ textAlign: "right" }}>
                    <div style={{ fontSize: "var(--c-font-xs, 12px)", color: colors.textMuted }}>仓位比</div>
                    <div style={{ fontFamily: "var(--c-font-mono)", fontWeight: 700, fontSize: 16, color: "var(--c-primary)" }}>
                      {summary.total_position_pct.toFixed(1)}%
                    </div>
                  </div>
                ) : null}
              </div>

              {/* 仓位双色进度条与重仓占比 */}
              {summary.cash_configured && summary.total_position_pct != null ? (
                <div style={{ margin: "10px 0 16px" }} className="portfolio-position-bar-container">
                  <div style={{
                    display: "flex",
                    justifyContent: "space-between",
                    fontSize: "var(--c-font-xs, 12px)",
                    marginBottom: 4,
                    color: colors.textMuted,
                  }}>
                    <span>持仓 {masked ? "••••••" : formatMoney(summary.total_market_value)} ({positionPct.toFixed(1)}%)</span>
                    <span>现金 {masked ? "••••••" : formatMoney(summary.cash_balance)} ({cashPct.toFixed(1)}%)</span>
                  </div>
                  <div style={{
                    height: 6,
                    borderRadius: 3,
                    background: colors.nestedBg,
                    overflow: "hidden",
                    display: "flex",
                  }}>
                    {stocks && stocks.length > 0 ? (
                      stocks.slice(0, 5).map((stock, i) => {
                        const stockPct = ((stock.market_value ?? 0) / (summary.total_asset_value || 1)) * 100;
                        return (
                          <div
                            key={stock.stock_code}
                            style={{
                              width: `${Math.min(100, Math.max(0, stockPct))}%`,
                              background: HOLDING_PALETTE[i % HOLDING_PALETTE.length],
                              transition: "width 0.3s ease",
                            }}
                            title={`${stock.stock_name}: ${stockPct.toFixed(1)}%`}
                          />
                        );
                      })
                    ) : (
                      <div
                        style={{
                          width: `${Math.min(100, Math.max(0, positionPct))}%`,
                          background: "var(--c-primary)",
                          transition: "width 0.3s ease",
                        }}
                      />
                    )}
                    <div
                      style={{
                        width: `${Math.min(100, Math.max(0, cashPct))}%`,
                        background: colors.down ?? "#52c41a",
                        transition: "width 0.3s ease",
                      }}
                      title={`现金: ${cashPct.toFixed(1)}%`}
                    />
                  </div>

                  {/* 重仓股票分布微缩图例 */}
                  {stocks && stocks.length > 0 ? (
                    <div style={{ marginTop: 8, display: "flex", flexWrap: "wrap", gap: "4px 10px", fontSize: "var(--c-font-xs)" }}>
                      {stocks.slice(0, 4).map((st, i) => (
                        <span key={st.stock_code} style={{ display: "inline-flex", alignItems: "center", gap: 4 }}>
                          <span style={{ width: 6, height: 6, borderRadius: "50%", background: HOLDING_PALETTE[i % HOLDING_PALETTE.length] }} />
                          <span style={{ color: colors.textSecondary }}>{st.stock_name}</span>
                          <span style={{ fontWeight: 600, fontFamily: "var(--c-font-mono)", color: colors.textMuted }}>
                            {st.allocation_pct != null ? `${st.allocation_pct.toFixed(1)}%` : "-"}
                          </span>
                        </span>
                      ))}
                      <span style={{ display: "inline-flex", alignItems: "center", gap: 4 }}>
                        <span style={{ width: 6, height: 6, borderRadius: "50%", background: colors.down ?? "#52c41a" }} />
                        <span style={{ color: colors.textSecondary }}>现金</span>
                        <span style={{ fontWeight: 600, fontFamily: "var(--c-font-mono)", color: colors.textMuted }}>
                          {cashPct.toFixed(1)}%
                        </span>
                      </span>
                    </div>
                  ) : null}
                </div>
              ) : null}
            </div>

            {/* 当日、浮动、综合三项关键收益指标 */}
            <div
              style={{
                background: colors.nestedBg,
                borderRadius: 8,
                padding: "var(--c-pad-inset, 7px 12px)",
                marginTop: 8,
              }}
              className="portfolio-hero-pnl-strip"
            >
              <Row gutter={[12, 8]}>
                <Col xs={8}>
                  <Statistic
                    className="portfolio-summary-stat"
                    title={<span><ThunderboltOutlined style={{ marginRight: 4 }} />当日盈亏</span>}
                    value={hasDailyProfit ? summary.daily_profit_amount : "-"}
                    precision={2}
                    prefix={hasDailyProfit ? "¥" : undefined}
                    styles={{
                      content: {
                        fontFamily: "var(--c-font-mono)",
                        fontWeight: 700,
                        fontSize: 15,
                        color: changeColor(hasDailyProfit ? summary.daily_profit_amount : null, colors),
                      },
                    }}
                  />
                  <Text className="portfolio-summary-subtext" style={{ color: colors.textMuted, fontSize: "var(--c-font-xs)" }}>
                    昨收市值 {formatMoney(summary.previous_close_value)}
                    {summary.daily_profit_pct == null ? "" : ` · ${summary.daily_profit_pct.toFixed(2)}%`}
                  </Text>
                </Col>

                <Col xs={8}>
                  <Statistic
                    className="portfolio-summary-stat"
                    title={<span><RiseOutlined style={{ marginRight: 4 }} />浮动盈亏</span>}
                    value={summary.unrealized_profit_amount}
                    precision={2}
                    prefix="¥"
                    styles={{
                      content: {
                        fontFamily: "var(--c-font-mono)",
                        fontWeight: 700,
                        fontSize: 15,
                        color: changeColor(summary.unrealized_profit_amount, colors),
                      },
                    }}
                  />
                  <Text className="portfolio-summary-subtext" style={{ color: colors.textMuted, fontSize: "var(--c-font-xs)" }}>
                    盈利 {summary.profitable_count} · 亏损 {summary.losing_count}
                  </Text>
                </Col>

                <Col xs={8}>
                  <Statistic
                    className="portfolio-summary-stat"
                    title={<span><FundOutlined style={{ marginRight: 4 }} />综合盈亏</span>}
                    value={summary.combined_profit_amount}
                    precision={2}
                    prefix="¥"
                    styles={{
                      content: {
                        fontFamily: "var(--c-font-mono)",
                        fontWeight: 700,
                        fontSize: 15,
                        color: changeColor(summary.combined_profit_amount, colors),
                      },
                    }}
                  />
                  <Text className="portfolio-summary-subtext" style={{ color: colors.textMuted, fontSize: "var(--c-font-xs)" }}>
                    共 {summary.transaction_count} 笔交易流水
                  </Text>
                </Col>
              </Row>
            </div>
          </Card>
        </Col>

        {/* 右侧：次级资金与持仓指标网格 */}
        <Col xs={24} lg={10} xl={10}>
          <Row gutter={[8, 8]} style={{ height: "100%" }}>
            <Col xs={12} sm={8} lg={12}>
              <Card
                size="small"
                style={{
                  ...cardStyle,
                  borderLeft: `3px solid ${changeColor(summary.cash_balance, colors)}`,
                }}
                className="u-card-interactive portfolio-summary-card"
              >
                <Statistic
                  className="portfolio-summary-stat"
                  title={<span><WalletOutlined style={{ marginRight: 4 }} />现金余额</span>}
                  value={summary.cash_balance ?? "-"}
                  precision={2}
                  prefix={summary.cash_balance == null ? undefined : "¥"}
                  styles={{
                    content: {
                      fontFamily: "var(--c-font-mono)",
                      fontWeight: 700,
                      color: changeColor(summary.cash_balance, colors),
                    },
                  }}
                />
                <Text className="portfolio-summary-subtext" style={{ color: colors.textMuted, fontSize: "var(--c-font-sm)" }}>
                  初始资金 {formatMoney(summary.initial_cash)}
                </Text>
              </Card>
            </Col>

            <Col xs={12} sm={8} lg={12}>
              <Card
                size="small"
                style={{
                  ...cardStyle,
                  borderLeft: "3px solid #722ed1",
                }}
                className="u-card-interactive portfolio-summary-card"
              >
                <Statistic
                  className="portfolio-summary-stat"
                  title={<span><PieChartOutlined style={{ marginRight: 4 }} />总仓位</span>}
                  value={summary.total_position_pct ?? "-"}
                  precision={2}
                  suffix={summary.total_position_pct == null ? undefined : "%"}
                  styles={{ content: { fontFamily: "var(--c-font-mono)", fontWeight: 700 } }}
                />
                <Text className="portfolio-summary-subtext" style={{ color: colors.textMuted, fontSize: "var(--c-font-sm)" }}>
                  按总资产口径计算
                </Text>
              </Card>
            </Col>

            <Col xs={12} sm={8} lg={12}>
              <Card
                size="small"
                style={{
                  ...cardStyle,
                  borderLeft: "3px solid var(--c-primary)",
                }}
                className="u-card-interactive portfolio-summary-card"
              >
                <Statistic
                  className="portfolio-summary-stat"
                  title={<span><StockOutlined style={{ marginRight: 4 }} />最新市值</span>}
                  value={summary.total_market_value}
                  precision={2}
                  prefix="¥"
                  styles={{ content: { fontFamily: "var(--c-font-mono)", fontWeight: 700 } }}
                />
                <Text className="portfolio-summary-subtext" style={{ color: colors.textMuted, fontSize: "var(--c-font-sm)" }}>
                  已定价成本 {formatMoney(summary.priced_cost)}
                </Text>
              </Card>
            </Col>

            <Col xs={12} sm={8} lg={12}>
              <Card
                size="small"
                style={{
                  ...cardStyle,
                  borderLeft: `3px solid ${changeColor(summary.total_profit_pct, colors)}`,
                }}
                className="u-card-interactive portfolio-summary-card"
              >
                <Statistic
                  className="portfolio-summary-stat"
                  title={<span><LineChartOutlined style={{ marginRight: 4 }} />浮动收益率</span>}
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
                <Text className="portfolio-summary-subtext" style={{ color: colors.textMuted, fontSize: "var(--c-font-sm)" }}>
                  基于已定价持仓计算
                </Text>
              </Card>
            </Col>

            <Col xs={12} sm={8} lg={12}>
              <Card
                size="small"
                style={{
                  ...cardStyle,
                  borderLeft: "3px solid #1890ff",
                }}
                className="u-card-interactive portfolio-summary-card"
              >
                <Statistic
                  className="portfolio-summary-stat"
                  title={<span><StockOutlined style={{ marginRight: 4 }} />持仓总成本</span>}
                  value={summary.total_cost}
                  precision={2}
                  prefix="¥"
                  styles={{ content: { fontFamily: "var(--c-font-mono)", fontWeight: 700 } }}
                />
                <Text className="portfolio-summary-subtext" style={{ color: colors.textMuted, fontSize: "var(--c-font-sm)" }}>
                  {summary.stock_count} 只股票 · {summary.position_count} 个剩余批次
                </Text>
              </Card>
            </Col>

            <Col xs={12} sm={8} lg={12}>
              <Card
                size="small"
                style={{
                  ...cardStyle,
                  borderLeft: `3px solid ${changeColor(summary.realized_profit_amount, colors)}`,
                }}
                className="u-card-interactive portfolio-summary-card"
              >
                <Statistic
                  className="portfolio-summary-stat"
                  title={<span><CheckCircleOutlined style={{ marginRight: 4 }} />已实现盈亏</span>}
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
                <Text className="portfolio-summary-subtext" style={{ color: colors.textMuted, fontSize: "var(--c-font-sm)" }}>
                  按 FIFO 成本核算卖出
                </Text>
              </Card>
            </Col>
          </Row>
        </Col>
      </Row>
    </>
  );
}
