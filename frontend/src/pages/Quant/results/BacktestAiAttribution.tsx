import { useMemo, useState } from "react";
import {
  BulbOutlined,
  CheckCircleOutlined,
  CopyOutlined,
  DashboardOutlined,
  SafetyCertificateOutlined,
  StarOutlined,
  ThunderboltOutlined,
} from "@ant-design/icons";
import { Button, Card, Col, message, Progress, Row, Space, Tag, Typography } from "antd";
import type { QuantBacktestResult, QuantStrategyConfig } from "../../../api/queries";
import { useAddWatchlistItem } from "../../../api/queries";
import { useColors, useStyles } from "../../../styles/ui";
import { formatNumber, formatPercent } from "./formatters";
import { quantStrategyIdentity } from "../quantRun";

const { Paragraph } = Typography;

interface BacktestAiAttributionProps {
  result: QuantBacktestResult;
  strategy?: QuantStrategyConfig;
}

export default function BacktestAiAttribution({ result, strategy }: BacktestAiAttributionProps) {
  const colors = useColors();
  const { cardStyle } = useStyles();
  const addWatchlistItem = useAddWatchlistItem();
  const [addingWatchlist, setAddingWatchlist] = useState(false);
  const [addedAll, setAddedAll] = useState(false);

  const metrics = result.metrics;
  const codes = result.codes;

  // Diagnostic logic based on metrics and factors
  const diagnosis = useMemo(() => {
    const totalReturn = metrics.total_return ?? 0;
    const excess = metrics.excess_return ?? 0;
    const maxDd = Math.abs(metrics.max_drawdown ?? 0);
    const sharpe = metrics.sharpe_ratio ?? 0;
    const winRate = metrics.win_rate ?? 50;
    const plRatio = metrics.profit_loss_ratio ?? 1;
    const alpha = metrics.alpha ?? 0;

    // Health Score calculation (0 - 100)
    let score = 50;
    if (sharpe >= 1.5) score += 20;
    else if (sharpe >= 1.0) score += 12;
    else if (sharpe < 0.5) score -= 15;

    if (excess > 10) score += 15;
    else if (excess > 0) score += 8;
    else score -= 10;

    if (maxDd < 10) score += 15;
    else if (maxDd < 18) score += 5;
    else if (maxDd > 25) score -= 15;

    if (plRatio >= 1.8) score += 10;
    else if (plRatio < 1.0) score -= 10;

    const clampedScore = Math.max(20, Math.min(98, Math.round(score)));

    // Archetype and badges
    let archetype = "均衡型策略";
    let archetypeColor = "blue";
    if (sharpe >= 1.2 && maxDd <= 15) {
      archetype = "稳健超额型 (High Alpha & Low Drawdown)";
      archetypeColor = "success";
    } else if (totalReturn > 20 && maxDd > 20) {
      archetype = "高波弹性动量型 (High Volatility Momentum)";
      archetypeColor = "orange";
    } else if (winRate >= 60) {
      archetype = "高胜率波段防御型 (High Win-rate Defense)";
      archetypeColor = "cyan";
    } else if (excess < 0) {
      archetype = "震荡市磨损型 (Range-bound Frictional)";
      archetypeColor = "default";
    }

    return {
      score: clampedScore,
      archetype,
      archetypeColor,
      isExcessPositive: excess > 0,
      isHighAlpha: alpha > 3,
      isLowDrawdown: maxDd <= 15,
      isHighWinRate: winRate >= 55,
      isGoodPayoff: plRatio >= 1.5,
    };
  }, [metrics]);

  const handleBatchAddToWatchlist = async () => {
    if (!codes.length) {
      message.info("暂无标的可加入自选");
      return;
    }
    setAddingWatchlist(true);
    let successCount = 0;
    try {
      for (const code of codes) {
        try {
          await addWatchlistItem.mutateAsync({
            stock_code: code,
            note: `量化回测优选(${strategy?.name || "量化策略"})`,
          });
          successCount++;
        } catch {
          // ignore duplicate or single failure
        }
      }
      setAddedAll(true);
      message.success(`已将 ${successCount} 只回测标的成功加入自选股`);
    } catch {
      message.error("加入自选出现异常，请稍后重试");
    } finally {
      setAddingWatchlist(false);
    }
  };

  const handleCopyAttribution = async () => {
    const report = [
      `### AI 策略战术归因体检报告`,
      `- 策略：${strategy ? quantStrategyIdentity(strategy) : "量化策略"}`,
      `- 综合成色评分：${diagnosis.score} 分 · ${diagnosis.archetype}`,
      `- 累计收益：${formatPercent(metrics.total_return)} (超额: ${formatPercent(metrics.excess_return)})`,
      `- 风险收益比：夏普 ${metrics.sharpe_ratio ?? "-"} ｜ 最大回撤 ${formatPercent(metrics.max_drawdown)}`,
      `- 核心胜负手：胜率 ${metrics.win_rate != null ? `${metrics.win_rate.toFixed(1)}%` : "-"} ｜ 盈亏比 ${metrics.profit_loss_ratio ?? "-"}`,
      `- 换手与资金流建议：建议在开仓时结合日均换手率 > 2.5% 及主力资金净流入进行假突破过滤`,
      `- 基本面建议：配合 ROE > 10% 与低估值分位作为选股底池，规避个股基本面黑天鹅`,
    ].join("\n");
    try {
      await navigator.clipboard.writeText(report);
      message.success("AI 策略归因报告已复制到剪贴板");
    } catch {
      message.error("复制失败，请手动选择");
    }
  };

  return (
    <Card
      title={(
        <span style={{ display: "inline-flex", alignItems: "center", gap: 6 }}>
          <BulbOutlined style={{ color: "var(--c-primary)", fontSize: 16 }} />
          <span>AI 策略战术归因与多因子体检 (Tactical Attribution)</span>
          <Tag color={diagnosis.archetypeColor}>{diagnosis.archetype}</Tag>
        </span>
      )}
      extra={(
        <Space size={8} wrap>
          <Button
            size="small"
            icon={<CopyOutlined />}
            onClick={handleCopyAttribution}
            aria-label="复制AI归因报告"
          >
            复制归因报告
          </Button>
          {codes.length > 0 && (
            <Button
              size="small"
              type="primary"
              ghost
              icon={addedAll ? <CheckCircleOutlined /> : <StarOutlined />}
              onClick={handleBatchAddToWatchlist}
              loading={addingWatchlist}
              disabled={addedAll}
              aria-label="批量加自选"
            >
              {addedAll ? "已加入自选" : "一键批量加自选"}
            </Button>
          )}
        </Space>
      )}
      size="small"
      style={{ ...cardStyle, marginBottom: 16 }}
      className="quant-result-card"
    >
      <Row gutter={[16, 16]}>
        {/* Score & Core Evaluation */}
        <Col xs={24} md={8}>
          <div
            style={{
              padding: "16px",
              height: "100%",
              borderRadius: "var(--c-radius-sm)",
              background: "color-mix(in srgb, var(--c-primary) 5%, var(--c-nested-bg))",
              border: "1px solid color-mix(in srgb, var(--c-primary) 18%, var(--c-border))",
              display: "flex",
              flexDirection: "column",
              justifyContent: "space-between",
            }}
          >
            <div>
              <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center" }}>
                <span style={{ fontSize: 13, color: "var(--c-text-muted)" }}>策略成色综合评级</span>
                <span
                  style={{
                    fontSize: 24,
                    fontWeight: 800,
                    fontFamily: "var(--c-font-mono)",
                    color: diagnosis.score >= 70 ? colors.up : colors.textPrimary,
                  }}
                >
                  {diagnosis.score}
                  <span style={{ fontSize: 13, fontWeight: 500, color: "var(--c-text-muted)" }}>/100</span>
                </span>
              </div>
              <Progress
                percent={diagnosis.score}
                showInfo={false}
                strokeColor={{ "0%": "var(--c-primary)", "100%": colors.up }}
                size="small"
                style={{ marginTop: 6, marginBottom: 12 }}
              />
              <div style={{ fontSize: 13, lineHeight: 1.6, color: "var(--c-text-primary)" }}>
                {diagnosis.isExcessPositive ? (
                  <p style={{ margin: 0 }}>
                    🎯 <strong>显著跑赢基准：</strong>
                    区间累计产生 <span style={{ color: colors.up }}>+{metrics.excess_return?.toFixed(1)}%</span> 超额回报。
                  </p>
                ) : (
                  <p style={{ margin: 0, color: "var(--c-text-muted)" }}>
                    ⚖️ <strong>超额偏弱：</strong>
                    当前策略在回测区间与基准收益接近，可能受到市场风格或持仓摩擦影响。
                  </p>
                )}
                <p style={{ margin: "6px 0 0", fontSize: 12, color: "var(--c-text-muted)" }}>
                  夏普比率 <strong>{metrics.sharpe_ratio ?? "-"}</strong> ｜ 最大回撤{" "}
                  <strong>{formatPercent(metrics.max_drawdown)}</strong> ｜ 盈亏比{" "}
                  <strong>{formatNumber(metrics.profit_loss_ratio)}:1</strong>
                </p>
              </div>
            </div>

            <div style={{ display: "flex", flexWrap: "wrap", gap: 4, marginTop: 12 }}>
              {diagnosis.isHighAlpha && <Tag color="green">超额阿尔法强劲</Tag>}
              {diagnosis.isLowDrawdown && <Tag color="blue">回撤控制扎实</Tag>}
              {diagnosis.isGoodPayoff && <Tag color="purple">盈亏比优势显著</Tag>}
              {diagnosis.isHighWinRate && <Tag color="cyan">高胜率支撑</Tag>}
            </div>
          </div>
        </Col>

        {/* Multi-Factor Insights (Capital Flow, Turnover, Financials) */}
        <Col xs={24} md={16}>
          <div style={{ display: "flex", flexDirection: "column", gap: 12 }}>
            {/* Factor 1: Turnover & Volume Dynamics */}
            <div
              style={{
                padding: "var(--c-pad-inset, 7px 12px)",
                borderRadius: "var(--c-radius-sm)",
                background: "var(--c-nested-bg)",
                border: "1px solid var(--c-border)",
              }}
            >
              <div style={{ display: "flex", alignItems: "center", gap: 6, marginBottom: 4 }}>
                <ThunderboltOutlined style={{ color: "#fa8c16" }} />
                <strong style={{ fontSize: 13 }}>换手率与量价活跃度归因</strong>
                <Tag color="orange" style={{ margin: 0, fontSize: 11 }}>流动性特征</Tag>
              </div>
              <Paragraph style={{ margin: 0, fontSize: 12, color: "var(--c-text-muted)", lineHeight: 1.6 }}>
                回测年化换手率约 <strong>{formatPercent(metrics.turnover_rate)}</strong>。
                {metrics.turnover_rate > 200
                  ? " 该策略交易节奏较为进取。在个股量价放量初期（换手率突破 3%~5%）进场往往胜率更高；但在个股缩量阴跌期需严格执行止损，防止流动性滑点损失。"
                  : " 该策略属于中低频波段持有，对短期交易杂波具备良好免疫力，换手摩擦成本较低，适合中线趋势跟踪。"}
              </Paragraph>
            </div>

            {/* Factor 2: Capital Flow & Momentum */}
            <div
              style={{
                padding: "var(--c-pad-inset, 7px 12px)",
                borderRadius: "var(--c-radius-sm)",
                background: "var(--c-nested-bg)",
                border: "1px solid var(--c-border)",
              }}
            >
              <div style={{ display: "flex", alignItems: "center", gap: 6, marginBottom: 4 }}>
                <DashboardOutlined style={{ color: "var(--c-primary)" }} />
                <strong style={{ fontSize: 13 }}>资金流向与主力博弈协同建议</strong>
                <Tag color="geekblue" style={{ margin: 0, fontSize: 11 }}>资金面赋能</Tag>
              </div>
              <Paragraph style={{ margin: 0, fontSize: 12, color: "var(--c-text-muted)", lineHeight: 1.6 }}>
                实盘量化进阶建议：将<strong>「主力资金连续净流入」</strong>或<strong>「超大单成交占比 &gt; 10%」</strong>作为策略买点的正向过滤条件，能有效规避散户追高被套诱多陷阱，提升假突破过滤效率。
              </Paragraph>
            </div>

            {/* Factor 3: Fundamentals & Valuation Gate */}
            <div
              style={{
                padding: "var(--c-pad-inset, 7px 12px)",
                borderRadius: "var(--c-radius-sm)",
                background: "var(--c-nested-bg)",
                border: "1px solid var(--c-border)",
              }}
            >
              <div style={{ display: "flex", alignItems: "center", gap: 6, marginBottom: 4 }}>
                <SafetyCertificateOutlined style={{ color: "#52c41a" }} />
                <strong style={{ fontSize: 13 }}>财报基本面与选股池质量底座</strong>
                <Tag color="green" style={{ margin: 0, fontSize: 11 }}>安全边际</Tag>
              </div>
              <Paragraph style={{ margin: 0, fontSize: 12, color: "var(--c-text-muted)", lineHeight: 1.6 }}>
                结合智能选股（Screener）构建底池时，建议前置叠加<strong>「ROE ≥ 10% + 扣非净利润连续增长 + 估值处历史 50% 分位以内」</strong>。优质基本面可提供坚实下行安全垫，避免纯技术择时买入业绩暴雷个股。
              </Paragraph>
            </div>
          </div>
        </Col>
      </Row>
    </Card>
  );
}
