import React from "react";
import { Alert, Button, Card, Col, Row, Space, Statistic, Tag, Typography } from "antd";
import {
  AlertOutlined,
  CheckCircleOutlined,
  SafetyCertificateOutlined,
  ThunderboltOutlined,
} from "@ant-design/icons";
import type { PortfolioRiskSummary, PortfolioTrimSuggestion } from "../../types/portfolio";
import type { SemanticTagColor } from "../../theme/hooks";
import { formatInteger, formatMoney } from "./portfolioFormatters";
import "./portfolio-risk-panel.css";

const { Text } = Typography;

function formatPct(value: number | null | undefined) {
  return value == null ? "-" : `${value.toFixed(2)}%`;
}

interface PortfolioRiskPanelProps {
  risk: PortfolioRiskSummary;
  /** 点击减仓建议时把股票与建议股数预填到卖出表单。 */
  onUseSuggestion?: (suggestion: PortfolioTrimSuggestion) => void;
}

const levelMeta: Record<PortfolioRiskSummary["concentration_level"], { color: SemanticTagColor; label: string; icon: typeof CheckCircleOutlined }> = {
  low: { color: "down", label: "低风险", icon: CheckCircleOutlined },
  medium: { color: "warning", label: "中风险", icon: AlertOutlined },
  high: { color: "up", label: "高风险", icon: ThunderboltOutlined },
  unknown: { color: "info", label: "待评估", icon: SafetyCertificateOutlined },
};

const SECTOR_PALETTE = [
  "#1677ff",
  "#52c41a",
  "#faad14",
  "#722ed1",
  "#13c2c2",
  "#eb2f96",
  "#fa8c16",
  "#2f54eb",
];

export default function PortfolioRiskPanel({ risk, onUseSuggestion }: PortfolioRiskPanelProps) {
  const level = levelMeta[risk.concentration_level];
  const LevelIcon = level.icon;

  const largestPosition = risk.largest_position_stock_name && risk.largest_position_stock_code
    ? `${risk.largest_position_stock_name} · ${risk.largest_position_stock_code}`
    : "暂无可评估持仓";
  const largestSector = risk.largest_sector_name ?? "暂无行业归属";

  // 计算超限状态
  const isStockOverLimit = (risk.max_single_stock_pct ?? 0) > risk.max_single_stock_limit_pct;
  const isSectorOverLimit = (risk.largest_sector_pct ?? 0) > risk.max_sector_limit_pct;

  return (
    <Card
      size="small"
      title={
        <Space size={6}>
          <SafetyCertificateOutlined className="portfolio-risk-panel__title-icon" />
          <span>仓位风险</span>
        </Space>
      }
      extra={
        <Tag className={`portfolio-risk-panel__level-tag portfolio-risk-panel__level-tag--${level.color}`}>
          <Space size={4}>
            <LevelIcon className="portfolio-risk-panel__level-icon" />
            <span>{level.label}</span>
          </Space>
        </Tag>
      }
      className="portfolio-risk-card u-card"
    >
      {/* 核心风控阈值与持仓权重对比 */}
      <div className="portfolio-risk-panel__metrics-section">
        <Row gutter={[12, 12]}>
          <Col xs={12} md={6}>
            <div className="portfolio-risk-panel__stat-box">
              <Statistic
                className="portfolio-risk-stat"
                title="总仓位上限"
                value={risk.max_total_position_limit_pct}
                precision={2}
                suffix="%"
              />
              <Text className="portfolio-risk-subtext u-block">
                剩余可加仓 {risk.remaining_add_capacity == null ? "配置资金后估算" : formatMoney(risk.remaining_add_capacity)}
                {risk.remaining_add_capacity == null ? "" : "（未扣费用）"}
              </Text>
            </div>
          </Col>

          <Col xs={12} md={6}>
            <div className={`portfolio-risk-panel__stat-box ${isStockOverLimit ? "portfolio-risk-panel__stat-box--overlimit" : ""}`}>
              <Statistic
                className="portfolio-risk-stat"
                title="最大单股权重"
                value={risk.max_single_stock_pct ?? "-"}
                precision={2}
                suffix={risk.max_single_stock_pct == null ? undefined : "%"}
              />
              <Text className="portfolio-risk-subtext u-block">
                {largestPosition}
              </Text>
              <Text className={`portfolio-risk-subtext ${isStockOverLimit ? "portfolio-risk-panel__overlimit-text" : ""}`}>
                上限 {risk.max_single_stock_limit_pct.toFixed(2)}%
                {isStockOverLimit ? " (超上限)" : ""}
              </Text>
            </div>
          </Col>

          <Col xs={12} md={6}>
            <div className={`portfolio-risk-panel__stat-box ${isSectorOverLimit ? "portfolio-risk-panel__stat-box--overlimit" : ""}`}>
              <Statistic
                className="portfolio-risk-stat"
                title="最大行业仓位"
                value={risk.largest_sector_pct ?? "-"}
                precision={2}
                suffix={risk.largest_sector_pct == null ? undefined : "%"}
              />
              <Text className="portfolio-risk-subtext u-block">
                {largestSector}
              </Text>
              <Text className={`portfolio-risk-subtext ${isSectorOverLimit ? "portfolio-risk-panel__overlimit-text" : ""}`}>
                上限 {risk.max_sector_limit_pct.toFixed(2)}%
                {isSectorOverLimit ? " (超上限)" : ""}
              </Text>
            </div>
          </Col>

          <Col xs={12} md={6}>
            <div className="portfolio-risk-panel__stat-box">
              <Statistic
                className="portfolio-risk-stat"
                title="前三大持仓占比"
                value={risk.top3_concentration_pct ?? "-"}
                precision={2}
                suffix={risk.top3_concentration_pct == null ? undefined : "%"}
              />
              <Text className="portfolio-risk-subtext u-block">
                已定价 {risk.priced_stock_count} 只
                {risk.unpriced_stock_count > 0 ? ` · 未定价 ${risk.unpriced_stock_count} 只` : ""}
              </Text>
            </div>
          </Col>
        </Row>
      </div>

      {/* 集中度与分散度详细指标 */}
      <div className="portfolio-risk-panel__details-box">
        <div className="portfolio-risk-panel__details-title">
          组合分散度与集中度指标
        </div>
        <Row gutter={[12, 10]}>
          <Col xs={12} md={6}>
            <Statistic
              className="portfolio-risk-stat"
              title="前五大持仓（含现金）"
              value={risk.top5_concentration_pct ?? "-"}
              precision={2}
              suffix={risk.top5_concentration_pct == null ? undefined : "%"}
            />
            <Text className="portfolio-risk-subtext">
              前五大持仓合计权重（含现金总资产口径）
            </Text>
          </Col>
          <Col xs={12} md={6}>
            <Statistic
              className="portfolio-risk-stat"
              title="有效持仓数（含现金）"
              value={risk.effective_holding_count ?? "-"}
              precision={2}
            />
            <Text className="portfolio-risk-subtext">
              按含现金权重折算的等效分散度
            </Text>
          </Col>
          <Col xs={12} md={6}>
            <Statistic
              className="portfolio-risk-stat"
              title="集中度 HHI（含现金）"
              value={risk.concentration_index ?? "-"}
              precision={2}
            />
            <Text className="portfolio-risk-subtext">
              0-10000，越高越集中；含现金口径
            </Text>
          </Col>
          <Col xs={12} md={6}>
            <Statistic
              className="portfolio-risk-stat"
              title="现金占比"
              value={risk.cash_pct ?? "-"}
              precision={2}
              suffix={risk.cash_pct == null ? undefined : "%"}
            />
            <Text className="portfolio-risk-subtext">
              现金 / 总资产
            </Text>
          </Col>

          <Col xs={12} md={8}>
            <Statistic
              className="portfolio-risk-stat"
              title="证券前五大占比"
              value={risk.securities_top5_concentration_pct ?? "-"}
              precision={2}
              suffix={risk.securities_top5_concentration_pct == null ? undefined : "%"}
            />
            <Text className="portfolio-risk-subtext">
              仅按证券市值内部权重计算
            </Text>
          </Col>
          <Col xs={12} md={8}>
            <Statistic
              className="portfolio-risk-stat"
              title="证券有效持仓数"
              value={risk.securities_effective_holding_count ?? "-"}
              precision={2}
            />
            <Text className="portfolio-risk-subtext">
              剔除现金后的股票分散度
            </Text>
          </Col>
          <Col xs={12} md={8}>
            <Statistic
              className="portfolio-risk-stat"
              title="证券 HHI"
              value={risk.securities_concentration_index ?? "-"}
              precision={2}
            />
            <Text className="portfolio-risk-subtext">
              0-10000，仅衡量股票集中度
            </Text>
          </Col>
        </Row>
      </div>

      {/* 行业分布 */}
      {risk.sector_allocations?.length ? (
        <div className="portfolio-risk-panel__sector-section">
          <div className="portfolio-risk-panel__section-header">
            <Text strong className="portfolio-risk-panel__section-title">行业仓位</Text>
            <Text className="portfolio-risk-panel__section-limit">
              行业上限 {risk.max_sector_limit_pct.toFixed(2)}%
            </Text>
          </div>

          {/* 行业多段比例条 */}
          <div className="portfolio-risk-panel__bar-container">
            {risk.sector_allocations.map((sector, idx) => {
              const pct = Math.max(0, sector.allocation_pct ?? 0);
              if (pct <= 0) return null;
              const color = SECTOR_PALETTE[idx % SECTOR_PALETTE.length];
              const barStyle: React.CSSProperties = {
                width: `${pct}%`,
                backgroundColor: color,
              };
              return (
                <div
                  key={sector.sector_name}
                  className="portfolio-risk-panel__bar-item"
                  style={barStyle}
                  title={`${sector.sector_name}: ${pct.toFixed(2)}%`}
                />
              );
            })}
          </div>

          <Space wrap size={[8, 8]}>
            {risk.sector_allocations.map((sector, idx) => {
              const isOverLimit = (sector.allocation_pct ?? 0) > risk.max_sector_limit_pct;
              const color = SECTOR_PALETTE[idx % SECTOR_PALETTE.length];
              const dotStyle: React.CSSProperties = {
                backgroundColor: color,
              };
              return (
                <Tag
                  key={sector.sector_name}
                  className={`portfolio-risk-panel__sector-tag ${isOverLimit ? "portfolio-risk-panel__sector-tag--overlimit" : ""}`}
                >
                  <span
                    className="portfolio-risk-panel__sector-dot"
                    style={dotStyle}
                  />
                  {sector.sector_name} {sector.allocation_pct == null ? "-" : `${sector.allocation_pct.toFixed(2)}%`}
                  <Text className="portfolio-risk-panel__sector-meta">
                    {formatMoney(sector.market_value)} · {sector.stock_codes?.length ?? 0} 只
                  </Text>
                  {isOverLimit ? (
                    <Text className="portfolio-risk-panel__sector-warn">（超限）</Text>
                  ) : null}
                </Tag>
              );
            })}
          </Space>
        </div>
      ) : null}

      {/* 减仓建议 */}
      {risk.trim_suggestions?.length ? (
        <div className="portfolio-risk-panel__trim-section">
          <div className="portfolio-risk-panel__section-header">
            <Text strong className="portfolio-risk-panel__section-title">减仓建议</Text>
            <Text className="portfolio-risk-panel__section-limit">
              按最小交易单位向上取整，受可卖数量约束
            </Text>
          </div>
          <Space orientation="vertical" size={8} className="portfolio-risk-panel__trim-space">
            {risk.trim_suggestions.map((suggestion) => (
              <div
                key={suggestion.stock_code}
                className="portfolio-risk-panel__trim-card"
              >
                <div className="portfolio-risk-panel__trim-header">
                  <Space wrap size={[8, 4]}>
                    <Text strong>{suggestion.stock_name}（{suggestion.stock_code}）</Text>
                    <Tag color="warning" className="portfolio-risk-panel__trim-tag">
                      卖出 {formatInteger(suggestion.suggested_shares)} 股
                    </Tag>
                    <Text className="portfolio-risk-panel__trim-amount">≈ {formatMoney(suggestion.estimated_amount)}</Text>
                    <Text className="portfolio-risk-panel__trim-meta">
                      仓位 {formatPct(suggestion.current_pct)} → {formatPct(suggestion.target_pct)}
                      （可卖 {formatInteger(suggestion.sellable_shares)} 股，每手 {suggestion.lot_size} 股）
                    </Text>
                  </Space>
                  {onUseSuggestion ? (
                    <Button size="small" type="primary" onClick={() => onUseSuggestion(suggestion)}>
                      预填卖出
                    </Button>
                  ) : null}
                </div>
                <div className="portfolio-risk-panel__trim-reasons">
                  <Text className="portfolio-risk-panel__trim-reasons-text">
                    {suggestion.reasons?.join("；") ?? ""}
                  </Text>
                </div>
              </div>
            ))}
          </Space>
        </div>
      ) : null}

      {/* 风险提示警告 */}
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
          className="portfolio-risk-panel__alert"
        />
      ) : null}
    </Card>
  );
}
