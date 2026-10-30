import { Alert, Button, Card, Col, Row, Space, Statistic, Tag, Typography } from "antd";
import {
  AlertOutlined,
  CheckCircleOutlined,
  SafetyCertificateOutlined,
  ThunderboltOutlined,
} from "@ant-design/icons";
import type { PortfolioRiskSummary, PortfolioTrimSuggestion } from "../../types/portfolio";
import { useColors, useStyles, semanticTagStyle } from "../../styles/ui";
import type { SemanticTagColor } from "../../theme/hooks";
import { formatInteger, formatMoney } from "./portfolioFormatters";

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
  const colors = useColors();
  const { cardStyle } = useStyles();
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
          <SafetyCertificateOutlined style={{ color: "var(--c-primary)" }} />
          <span>仓位风险</span>
        </Space>
      }
      extra={
        <Tag style={semanticTagStyle(level.color)}>
          <Space size={4}>
            <LevelIcon style={{ fontSize: 12 }} />
            <span>{level.label}</span>
          </Space>
        </Tag>
      }
      style={{ ...cardStyle, marginBottom: 16 }}
      className="portfolio-risk-card"
    >
      {/* 核心风控阈值与持仓权重对比 */}
      <div style={{ marginBottom: 16 }}>
        <Row gutter={[12, 12]}>
          <Col xs={12} md={6}>
            <div style={{ padding: "var(--c-pad-inset, 7px 12px)", background: colors.nestedBg, borderRadius: 8, height: "100%" }}>
              <Statistic
                className="portfolio-risk-stat"
                title="总仓位上限"
                value={risk.max_total_position_limit_pct}
                precision={2}
                suffix="%"
              />
              <Text className="portfolio-risk-subtext" style={{ color: colors.textMuted, fontSize: "var(--c-font-sm)", display: "block" }}>
                剩余可加仓 {risk.remaining_add_capacity == null ? "配置资金后估算" : formatMoney(risk.remaining_add_capacity)}
                {risk.remaining_add_capacity == null ? "" : "（未扣费用）"}
              </Text>
            </div>
          </Col>

          <Col xs={12} md={6}>
            <div style={{
              padding: "var(--c-pad-inset, 7px 12px)",
              background: colors.nestedBg,
              borderRadius: 8,
              height: "100%",
              borderLeft: isStockOverLimit ? "3px solid var(--c-warning, #faad14)" : undefined,
            }}>
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
              <Text className="portfolio-risk-subtext" style={{ color: isStockOverLimit ? colors.warning : colors.textMuted, fontSize: "var(--c-font-sm)" }}>
                上限 {risk.max_single_stock_limit_pct.toFixed(2)}%
                {isStockOverLimit ? " (超上限)" : ""}
              </Text>
            </div>
          </Col>

          <Col xs={12} md={6}>
            <div style={{
              padding: "var(--c-pad-inset, 7px 12px)",
              background: colors.nestedBg,
              borderRadius: 8,
              height: "100%",
              borderLeft: isSectorOverLimit ? "3px solid var(--c-warning, #faad14)" : undefined,
            }}>
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
              <Text className="portfolio-risk-subtext" style={{ color: isSectorOverLimit ? colors.warning : colors.textMuted, fontSize: "var(--c-font-sm)" }}>
                上限 {risk.max_sector_limit_pct.toFixed(2)}%
                {isSectorOverLimit ? " (超上限)" : ""}
              </Text>
            </div>
          </Col>

          <Col xs={12} md={6}>
            <div style={{ padding: "var(--c-pad-inset, 7px 12px)", background: colors.nestedBg, borderRadius: 8, height: "100%" }}>
              <Statistic
                className="portfolio-risk-stat"
                title="前三大持仓占比"
                value={risk.top3_concentration_pct ?? "-"}
                precision={2}
                suffix={risk.top3_concentration_pct == null ? undefined : "%"}
              />
              <Text className="portfolio-risk-subtext" style={{ color: colors.textMuted, fontSize: "var(--c-font-sm)", display: "block" }}>
                已定价 {risk.priced_stock_count} 只
                {risk.unpriced_stock_count > 0 ? ` · 未定价 ${risk.unpriced_stock_count} 只` : ""}
              </Text>
            </div>
          </Col>
        </Row>
      </div>

      {/* 集中度与分散度详细指标 */}
      <div style={{
        border: `1px solid ${colors.border ?? "rgba(128,128,128,0.15)"}`,
        borderRadius: 8,
        padding: "var(--c-pad-inset, 7px 12px)",
        marginBottom: 12,
      }}>
        <div style={{ fontSize: "var(--c-font-xs, 12px)", color: colors.textMuted, marginBottom: 8, fontWeight: 600 }}>
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
            <Text className="portfolio-risk-subtext" style={{ color: colors.textMuted, fontSize: "var(--c-font-sm)" }}>
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
            <Text className="portfolio-risk-subtext" style={{ color: colors.textMuted, fontSize: "var(--c-font-sm)" }}>
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
            <Text className="portfolio-risk-subtext" style={{ color: colors.textMuted, fontSize: "var(--c-font-sm)" }}>
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
            <Text className="portfolio-risk-subtext" style={{ color: colors.textMuted, fontSize: "var(--c-font-sm)" }}>
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
            <Text className="portfolio-risk-subtext" style={{ color: colors.textMuted, fontSize: "var(--c-font-sm)" }}>
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
            <Text className="portfolio-risk-subtext" style={{ color: colors.textMuted, fontSize: "var(--c-font-sm)" }}>
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
            <Text className="portfolio-risk-subtext" style={{ color: colors.textMuted, fontSize: "var(--c-font-sm)" }}>
              0-10000，仅衡量股票集中度
            </Text>
          </Col>
        </Row>
      </div>

      {/* 行业分布 */}
      {risk.sector_allocations?.length ? (
        <div style={{ marginTop: 14 }}>
          <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center", marginBottom: 6 }}>
            <Text strong style={{ fontSize: "var(--c-font-sm, 13px)" }}>行业仓位</Text>
            <Text style={{ color: colors.textMuted, fontSize: "var(--c-font-xs)" }}>
              行业上限 {risk.max_sector_limit_pct.toFixed(2)}%
            </Text>
          </div>

          {/* 行业多段比例条 */}
          <div
            style={{
              display: "flex",
              height: 7,
              borderRadius: 4,
              overflow: "hidden",
              background: colors.nestedBg,
              marginBottom: 10,
            }}
          >
            {risk.sector_allocations.map((sector, idx) => {
              const pct = Math.max(0, sector.allocation_pct ?? 0);
              if (pct <= 0) return null;
              const color = SECTOR_PALETTE[idx % SECTOR_PALETTE.length];
              return (
                <div
                  key={sector.sector_name}
                  style={{
                    width: `${pct}%`,
                    backgroundColor: color,
                    transition: "width 0.3s ease",
                  }}
                  title={`${sector.sector_name}: ${pct.toFixed(2)}%`}
                />
              );
            })}
          </div>

          <Space wrap size={[8, 8]}>
            {risk.sector_allocations.map((sector, idx) => {
              const isOverLimit = (sector.allocation_pct ?? 0) > risk.max_sector_limit_pct;
              const color = SECTOR_PALETTE[idx % SECTOR_PALETTE.length];
              return (
                <Tag
                  key={sector.sector_name}
                  style={{
                    padding: "4px 8px",
                    borderRadius: 4,
                    borderColor: isOverLimit ? colors.warning : undefined,
                  }}
                >
                  <span
                    style={{
                      display: "inline-block",
                      width: 8,
                      height: 8,
                      borderRadius: "50%",
                      backgroundColor: color,
                      marginRight: 6,
                      verticalAlign: "middle",
                    }}
                  />
                  {sector.sector_name} {sector.allocation_pct == null ? "-" : `${sector.allocation_pct.toFixed(2)}%`}
                  <Text style={{ color: colors.textMuted, marginLeft: 6 }}>
                    {formatMoney(sector.market_value)} · {sector.stock_codes?.length ?? 0} 只
                  </Text>
                  {isOverLimit ? (
                    <Text style={{ color: colors.warning, marginLeft: 4, fontSize: 11 }}>（超限）</Text>
                  ) : null}
                </Tag>
              );
            })}
          </Space>
        </div>
      ) : null}

      {/* 减仓建议 */}
      {risk.trim_suggestions?.length ? (
        <div style={{ marginTop: 16 }}>
          <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center", marginBottom: 6 }}>
            <Text strong style={{ fontSize: "var(--c-font-sm, 13px)" }}>减仓建议</Text>
            <Text style={{ color: colors.textMuted, fontSize: "var(--c-font-xs)" }}>
              按最小交易单位向上取整，受可卖数量约束
            </Text>
          </div>
          <Space orientation="vertical" size={8} style={{ width: "100%" }}>
            {risk.trim_suggestions.map((suggestion) => (
              <div
                key={suggestion.stock_code}
                style={{
                  padding: "var(--c-pad-inset, 7px 12px)",
                  borderRadius: 8,
                  background: colors.nestedBg,
                  border: `1px solid ${colors.border ?? "rgba(128,128,128,0.15)"}`,
                }}
              >
                <div style={{ display: "flex", justifyContent: "space-between", alignItems: "flex-start", flexWrap: "wrap", gap: 8 }}>
                  <Space wrap size={[8, 4]}>
                    <Text strong>{suggestion.stock_name}（{suggestion.stock_code}）</Text>
                    <Tag color="warning" style={{ fontWeight: 600 }}>
                      卖出 {formatInteger(suggestion.suggested_shares)} 股
                    </Tag>
                    <Text style={{ fontWeight: 600 }}>≈ {formatMoney(suggestion.estimated_amount)}</Text>
                    <Text style={{ color: colors.textMuted }}>
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
                <div style={{ marginTop: 6 }}>
                  <Text style={{ color: colors.textMuted, fontSize: "var(--c-font-sm)" }}>
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
          style={{ marginTop: 14 }}
        />
      ) : null}
    </Card>
  );
}
