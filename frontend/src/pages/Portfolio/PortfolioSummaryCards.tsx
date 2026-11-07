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
import { useColors } from "../../styles/ui";
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
          className="portfolio-block-mb"
        />
      ) : null}

      {summary.fx_rates?.HKD != null ? (
        <Alert
          type="info"
          showIcon
          title="港股金额已折算为人民币"
          description={`当前折算汇率：1 HKD = ${summary.fx_rates.HKD} CNY。行情和成交价仍按港币展示，汇总市值、成本、盈亏和现金均以人民币计。`}
          className="portfolio-block-mb"
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
          className="portfolio-block-mb"
        />
      ) : null}

      <Row gutter={[12, 12]} className="portfolio-block-mb" align="stretch">
        {/* 左侧：主资产与盈亏核心看板 */}
        <Col xs={24} lg={14} xl={14}>
          <Card
            size="small"
            className="portfolio-hero-card u-card"
          >
            <div>
              <div className="portfolio-hero-top">
                <div>
                  <Statistic
                    className="portfolio-summary-stat portfolio-hero-stat"
                    title={
                      <span className="portfolio-hero-title">
                        <BankOutlined />
                        <span>总资产</span>
                        <Button
                          type="text"
                          size="small"
                          icon={masked ? <EyeInvisibleOutlined /> : <EyeOutlined />}
                          onClick={() => setMasked(!masked)}
                          className="portfolio-hero-mask-btn"
                          title={masked ? "显示金额" : "隐藏金额"}
                        />
                      </span>
                    }
                    value={masked ? "••••••" : (summary.total_asset_value ?? "-")}
                    precision={masked ? undefined : 2}
                    prefix={masked || summary.total_asset_value == null ? undefined : "¥"}
                  />
                  <Text className="portfolio-summary-subtext">
                    证券估值 {masked ? "••••••" : formatMoney(summary.estimated_securities_value)}
                  </Text>
                </div>

                {summary.cash_configured && summary.total_position_pct != null ? (
                  <div className="portfolio-hero-pos-badge">
                    <div className="portfolio-hero-pos-badge__label">仓位比</div>
                    <div className="portfolio-hero-pos-badge__val">
                      {summary.total_position_pct.toFixed(1)}%
                    </div>
                  </div>
                ) : null}
              </div>

              {/* 仓位双色进度条与重仓占比 */}
              {summary.cash_configured && summary.total_position_pct != null ? (
                <div className="portfolio-position-bar-container">
                  <div className="portfolio-position-bar__labels">
                    <span>持仓 {masked ? "••••••" : formatMoney(summary.total_market_value)} ({positionPct.toFixed(1)}%)</span>
                    <span>现金 {masked ? "••••••" : formatMoney(summary.cash_balance)} ({cashPct.toFixed(1)}%)</span>
                  </div>
                  <div className="portfolio-position-bar__track">
                    {stocks && stocks.length > 0 ? (
                      stocks.slice(0, 5).map((stock, i) => {
                        const stockPct = ((stock.market_value ?? 0) / (summary.total_asset_value || 1)) * 100;
                        return (
                          <div
                            key={stock.stock_code}
                            className="portfolio-position-bar__seg"
                            style={{
                              width: `${Math.min(100, Math.max(0, stockPct))}%`,
                              background: HOLDING_PALETTE[i % HOLDING_PALETTE.length],
                            }}
                            title={`${stock.stock_name}: ${stockPct.toFixed(1)}%`}
                          />
                        );
                      })
                    ) : (
                      <div
                        className="portfolio-position-bar__seg portfolio-position-bar__seg--primary"
                        style={{ width: `${Math.min(100, Math.max(0, positionPct))}%` }}
                      />
                    )}
                    <div
                      className="portfolio-position-bar__seg"
                      style={{
                        width: `${Math.min(100, Math.max(0, cashPct))}%`,
                        background: colors.down ?? "#52c41a",
                      }}
                      title={`现金: ${cashPct.toFixed(1)}%`}
                    />
                  </div>

                  {/* 重仓股票分布微缩图例 */}
                  {stocks && stocks.length > 0 ? (
                    <div className="portfolio-position-legend">
                      {stocks.slice(0, 4).map((st, i) => (
                        <span key={st.stock_code} className="portfolio-position-legend__item">
                          <span className="portfolio-position-legend__dot" style={{ background: HOLDING_PALETTE[i % HOLDING_PALETTE.length] }} />
                          <span className="portfolio-position-legend__name">{st.stock_name}</span>
                          <span className="portfolio-position-legend__pct">
                            {st.allocation_pct != null ? `${st.allocation_pct.toFixed(1)}%` : "-"}
                          </span>
                        </span>
                      ))}
                      <span className="portfolio-position-legend__item">
                        <span className="portfolio-position-legend__dot" style={{ background: colors.down ?? "#52c41a" }} />
                        <span className="portfolio-position-legend__name">现金</span>
                        <span className="portfolio-position-legend__pct">
                          {cashPct.toFixed(1)}%
                        </span>
                      </span>
                    </div>
                  ) : null}
                </div>
              ) : null}
            </div>

            {/* 当日、浮动、综合三项关键收益指标 */}
            <div className="portfolio-hero-pnl-strip">
              <Row gutter={[12, 8]}>
                <Col xs={8}>
                  <Statistic
                    className="portfolio-summary-stat"
                    title={<span><ThunderboltOutlined />当日盈亏</span>}
                    value={hasDailyProfit ? summary.daily_profit_amount : "-"}
                    precision={2}
                    prefix={hasDailyProfit ? "¥" : undefined}
                    styles={{
                      content: {
                        color: changeColor(hasDailyProfit ? summary.daily_profit_amount : null, colors),
                      },
                    }}
                  />
                  <Text className="portfolio-summary-subtext">
                    昨收市值 {formatMoney(summary.previous_close_value)}
                    {summary.daily_profit_pct == null ? "" : ` · ${summary.daily_profit_pct.toFixed(2)}%`}
                  </Text>
                </Col>

                <Col xs={8}>
                  <Statistic
                    className="portfolio-summary-stat"
                    title={<span><RiseOutlined />浮动盈亏</span>}
                    value={summary.unrealized_profit_amount}
                    precision={2}
                    prefix="¥"
                    styles={{
                      content: {
                        color: changeColor(summary.unrealized_profit_amount, colors),
                      },
                    }}
                  />
                  <Text className="portfolio-summary-subtext">
                    盈利 {summary.profitable_count} · 亏损 {summary.losing_count}
                  </Text>
                </Col>

                <Col xs={8}>
                  <Statistic
                    className="portfolio-summary-stat"
                    title={<span><FundOutlined />综合盈亏</span>}
                    value={summary.combined_profit_amount}
                    precision={2}
                    prefix="¥"
                    styles={{
                      content: {
                        color: changeColor(summary.combined_profit_amount, colors),
                      },
                    }}
                  />
                  <Text className="portfolio-summary-subtext">
                    共 {summary.transaction_count} 笔交易流水
                  </Text>
                </Col>
              </Row>
            </div>
          </Card>
        </Col>

        {/* 右侧：次级资金与持仓指标网格 */}
        <Col xs={24} lg={10} xl={10}>
          <Row gutter={[8, 8]} className="portfolio-summary-side-grid">
            <Col xs={12} sm={8} lg={12}>
              <Card
                size="small" style={{ borderLeft: `3px solid ${changeColor(summary.cash_balance, colors)}` }}
                className="u-card-interactive portfolio-summary-card u-card"
              >
                <Statistic
                  className="portfolio-summary-stat"
                  title={<span><WalletOutlined />现金余额</span>}
                  value={summary.cash_balance ?? "-"}
                  precision={2}
                  prefix={summary.cash_balance == null ? undefined : "¥"}
                  styles={{
                    content: {
                      color: changeColor(summary.cash_balance, colors),
                    },
                  }}
                />
                <Text className="portfolio-summary-subtext">
                  初始资金 {formatMoney(summary.initial_cash)}
                </Text>
              </Card>
            </Col>

            <Col xs={12} sm={8} lg={12}>
              <Card
                size="small"
                className="u-card-interactive portfolio-summary-card portfolio-summary-card--position u-card"
              >
                <Statistic
                  className="portfolio-summary-stat"
                  title={<span><PieChartOutlined />总仓位</span>}
                  value={summary.total_position_pct ?? "-"}
                  precision={2}
                  suffix={summary.total_position_pct == null ? undefined : "%"}
                />
                <Text className="portfolio-summary-subtext">
                  按总资产口径计算
                </Text>
              </Card>
            </Col>

            <Col xs={12} sm={8} lg={12}>
              <Card
                size="small"
                className="u-card-interactive portfolio-summary-card portfolio-summary-card--market u-card"
              >
                <Statistic
                  className="portfolio-summary-stat"
                  title={<span><StockOutlined />最新市值</span>}
                  value={summary.total_market_value}
                  precision={2}
                  prefix="¥"
                />
                <Text className="portfolio-summary-subtext">
                  已定价成本 {formatMoney(summary.priced_cost)}
                </Text>
              </Card>
            </Col>

            <Col xs={12} sm={8} lg={12}>
              <Card
                size="small" style={{ borderLeft: `3px solid ${changeColor(summary.total_profit_pct, colors)}` }}
                className="u-card-interactive portfolio-summary-card u-card"
              >
                <Statistic
                  className="portfolio-summary-stat"
                  title={<span><LineChartOutlined />浮动收益率</span>}
                  value={summary.total_profit_pct ?? "-"}
                  precision={2}
                  suffix={summary.total_profit_pct == null ? undefined : "%"}
                  styles={{
                    content: {
                      color: changeColor(summary.total_profit_pct, colors),
                    },
                  }}
                />
                <Text className="portfolio-summary-subtext">
                  基于已定价持仓计算
                </Text>
              </Card>
            </Col>

            <Col xs={12} sm={8} lg={12}>
              <Card
                size="small"
                className="u-card-interactive portfolio-summary-card portfolio-summary-card--cost u-card"
              >
                <Statistic
                  className="portfolio-summary-stat"
                  title={<span><StockOutlined />持仓总成本</span>}
                  value={summary.total_cost}
                  precision={2}
                  prefix="¥"
                />
                <Text className="portfolio-summary-subtext">
                  {summary.stock_count} 只股票 · {summary.position_count} 个剩余批次
                </Text>
              </Card>
            </Col>

            <Col xs={12} sm={8} lg={12}>
              <Card
                size="small" style={{ borderLeft: `3px solid ${changeColor(summary.realized_profit_amount, colors)}` }}
                className="u-card-interactive portfolio-summary-card u-card"
              >
                <Statistic
                  className="portfolio-summary-stat"
                  title={<span><CheckCircleOutlined />已实现盈亏</span>}
                  value={summary.realized_profit_amount}
                  precision={2}
                  prefix="¥"
                  styles={{
                    content: {
                      color: changeColor(summary.realized_profit_amount, colors),
                    },
                  }}
                />
                <Text className="portfolio-summary-subtext">
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
