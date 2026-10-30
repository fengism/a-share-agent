import { useMemo, useState } from "react";
import {
  CheckCircleOutlined,
  CloseOutlined,
  CopyOutlined,
  CrownOutlined,
  FundViewOutlined,
  SafetyCertificateOutlined,
  ThunderboltOutlined,
  TrophyOutlined,
} from "@ant-design/icons";
import { Badge, Button, Card, Col, Empty, Modal, Row, Table, Tag, Tooltip, Typography, message } from "antd";
import type { ColumnsType } from "antd/es/table";
import type { QuantBacktestRun } from "../../api/queries";
import { useColors } from "../../styles/ui";
import { quantStrategyLabel, quantUniverseLabel } from "./quantRun";

const { Text } = Typography;

export interface BacktestRunsComparatorModalProps {
  open: boolean;
  runs: QuantBacktestRun[];
  onClose: () => void;
  onSelectRun: (runId: string) => void;
  onRemoveRun?: (runId: string) => void;
}

interface WinnerHighlight {
  run: QuantBacktestRun;
  val: number;
}

interface RunHighlights {
  bestReturn: WinnerHighlight | null;
  bestSharpe: WinnerHighlight | null;
  minDrawdown: WinnerHighlight | null;
  bestWinRate: WinnerHighlight | null;
}

interface MetricRow {
  key: string;
  category: "收益回报" | "风险控制" | "风报比率" | "交易特征" | "策略配置";
  label: string;
  description: string;
  values: Record<string, string | number | null>;
  rawValues: Record<string, number | null>;
  higherIsBetter?: boolean;
}

export default function BacktestRunsComparatorModal({
  open,
  runs,
  onClose,
  onSelectRun,
  onRemoveRun,
}: BacktestRunsComparatorModalProps) {
  const colors = useColors();
  const [copied, setCopied] = useState(false);

  // 提取有效回测（有指标数据）
  const validRuns = useMemo(() => {
    return runs.filter((run) => Boolean(run.summary_metrics ?? run.result?.metrics));
  }, [runs]);

  // 计算四大胜出亮点
  const highlights = useMemo<RunHighlights | null>(() => {
    if (validRuns.length === 0) return null;

    let bestReturnRun: QuantBacktestRun | null = null;
    let maxReturn = -Infinity;

    let bestSharpeRun: QuantBacktestRun | null = null;
    let maxSharpe = -Infinity;

    let minDrawdownRun: QuantBacktestRun | null = null;
    let minDrawdownAbs = Infinity;

    let bestWinRateRun: QuantBacktestRun | null = null;
    let maxWinRate = -Infinity;

    validRuns.forEach((run) => {
      const m = run.summary_metrics ?? run.result?.metrics;
      if (!m) return;

      if (m.total_return > maxReturn) {
        maxReturn = m.total_return;
        bestReturnRun = run;
      }
      if (m.sharpe_ratio != null && m.sharpe_ratio > maxSharpe) {
        maxSharpe = m.sharpe_ratio;
        bestSharpeRun = run;
      }
      const absDd = Math.abs(m.max_drawdown);
      if (absDd < minDrawdownAbs) {
        minDrawdownAbs = absDd;
        minDrawdownRun = run;
      }
      if (m.win_rate != null && m.win_rate > maxWinRate) {
        maxWinRate = m.win_rate;
        bestWinRateRun = run;
      }
    });

    return {
      bestReturn: bestReturnRun ? { run: bestReturnRun, val: maxReturn } : null,
      bestSharpe: bestSharpeRun ? { run: bestSharpeRun, val: maxSharpe } : null,
      minDrawdown: minDrawdownRun ? { run: minDrawdownRun, val: minDrawdownAbs } : null,
      bestWinRate: bestWinRateRun ? { run: bestWinRateRun, val: maxWinRate } : null,
    };
  }, [validRuns]);

  // 构建对比行数据
  const metricRows = useMemo<MetricRow[]>(() => {
    if (validRuns.length === 0) return [];

    const getMetric = (run: QuantBacktestRun) => run.summary_metrics ?? run.result?.metrics;

    const buildRow = (
      key: string,
      category: MetricRow["category"],
      label: string,
      description: string,
      extractor: (run: QuantBacktestRun) => { formatted: string; raw: number | null },
      higherIsBetter?: boolean,
    ): MetricRow => {
      const values: Record<string, string> = {};
      const rawValues: Record<string, number | null> = {};
      validRuns.forEach((run) => {
        const res = extractor(run);
        values[run.id] = res.formatted;
        rawValues[run.id] = res.raw;
      });
      return { key, category, label, description, values, rawValues, higherIsBetter };
    };

    return [
      // 收益回报
      buildRow("total_return", "收益回报", "累计收益率", "整个回测周期策略产生的总回报", (run) => {
        const m = getMetric(run);
        if (m?.total_return == null) return { formatted: "-", raw: null };
        return {
          formatted: `${m.total_return > 0 ? "+" : ""}${m.total_return.toFixed(2)}%`,
          raw: m.total_return,
        };
      }, true),
      buildRow("annualized_return", "收益回报", "年化收益率 (CAGR)", "复利年化收益", (run) => {
        const m = getMetric(run);
        if (m?.annualized_return == null) return { formatted: "-", raw: null };
        return {
          formatted: `${m.annualized_return > 0 ? "+" : ""}${m.annualized_return.toFixed(2)}%`,
          raw: m.annualized_return,
        };
      }, true),
      buildRow("benchmark_return", "收益回报", "基准同期收益", "同期所选业绩基准指数的涨跌幅", (run) => {
        const m = getMetric(run);
        if (m?.benchmark_return == null) return { formatted: "-", raw: null };
        return {
          formatted: `${m.benchmark_return > 0 ? "+" : ""}${m.benchmark_return.toFixed(2)}%`,
          raw: m.benchmark_return,
        };
      }),
      buildRow("excess_return", "收益回报", "基准超额收益 (Alpha)", "策略相对基准指数的超额回报", (run) => {
        const m = getMetric(run);
        if (m?.excess_return == null) return { formatted: "-", raw: null };
        return {
          formatted: `${m.excess_return > 0 ? "+" : ""}${m.excess_return.toFixed(2)}%`,
          raw: m.excess_return,
        };
      }, true),

      // 风险控制
      buildRow("max_drawdown", "风险控制", "最大回撤", "资产净值从最高峰跌落至谷底的最大跌幅", (run) => {
        const m = getMetric(run);
        if (m?.max_drawdown == null) return { formatted: "-", raw: null };
        return {
          formatted: `-${Math.abs(m.max_drawdown).toFixed(2)}%`,
          raw: -Math.abs(m.max_drawdown),
        };
      }, true), // raw 是负数，越大代表回撤越小
      buildRow("annualized_volatility", "风险控制", "年化波动率", "策略收益率的标准差年化度量", (run) => {
        const m = getMetric(run);
        if (m?.annualized_volatility == null) return { formatted: "-", raw: null };
        return {
          formatted: `${m.annualized_volatility.toFixed(2)}%`,
          raw: -m.annualized_volatility, // 波动率小更好
        };
      }, true),
      buildRow("max_drawdown_duration", "风险控制", "最大回撤修复天数", "创出最大回撤到创新高所需的最长交易日", (run) => {
        const m = getMetric(run);
        if (m?.max_drawdown_duration_days == null) return { formatted: "-", raw: null };
        return {
          formatted: `${m.max_drawdown_duration_days} 天`,
          raw: -m.max_drawdown_duration_days,
        };
      }, true),

      // 风报比率
      buildRow("sharpe_ratio", "风报比率", "夏普比率 (Sharpe)", "每承受一单位总风险所获得的超额回报", (run) => {
        const m = getMetric(run);
        if (m?.sharpe_ratio == null) return { formatted: "-", raw: null };
        return {
          formatted: m.sharpe_ratio.toFixed(2),
          raw: m.sharpe_ratio,
        };
      }, true),
      buildRow("calmar_ratio", "风报比率", "卡玛比率 (Calmar)", "年化收益与最大回撤之比，衡量收益回撤效率", (run) => {
        const m = getMetric(run);
        if (m?.calmar_ratio == null) return { formatted: "-", raw: null };
        return {
          formatted: m.calmar_ratio.toFixed(2),
          raw: m.calmar_ratio,
        };
      }, true),
      buildRow("sortino_ratio", "风报比率", "索提诺比率 (Sortino)", "仅考虑下行波动率的风险调整后收益", (run) => {
        const m = getMetric(run);
        if (m?.sortino_ratio == null) return { formatted: "-", raw: null };
        return {
          formatted: m.sortino_ratio.toFixed(2),
          raw: m.sortino_ratio,
        };
      }, true),

      // 交易特征
      buildRow("win_rate", "交易特征", "胜率 (Win Rate)", "盈利交易笔数占所有已平仓交易的比例", (run) => {
        const m = getMetric(run);
        if (m?.win_rate == null) return { formatted: "-", raw: null };
        return {
          formatted: `${m.win_rate.toFixed(1)}%`,
          raw: m.win_rate,
        };
      }, true),
      buildRow("profit_loss_ratio", "交易特征", "盈亏比 (P/L Ratio)", "平均每笔盈利与平均每笔亏损的绝对值比例", (run) => {
        const m = getMetric(run);
        if (m?.profit_loss_ratio == null) return { formatted: "-", raw: null };
        return {
          formatted: m.profit_loss_ratio.toFixed(2),
          raw: m.profit_loss_ratio,
        };
      }, true),
      buildRow("trade_count", "交易特征", "总交易笔数", "回测周期内产生的买入/卖出委托笔数", (run) => {
        const m = getMetric(run);
        if (m?.trade_count == null) return { formatted: "-", raw: null };
        return {
          formatted: `${m.trade_count} 笔`,
          raw: m.trade_count,
        };
      }),
      buildRow("avg_holding_days", "交易特征", "平均持仓天数", "每笔头寸从建仓到平仓的平均持有自然交易日", (run) => {
        const m = getMetric(run);
        if (m?.avg_holding_days == null) return { formatted: "-", raw: null };
        return {
          formatted: `${m.avg_holding_days.toFixed(1)} 天`,
          raw: m.avg_holding_days,
        };
      }),
      buildRow("turnover_rate", "交易特征", "日均换手率", "回测中账户资产的每日周转活跃度", (run) => {
        const m = getMetric(run);
        if (m?.turnover_rate == null) return { formatted: "-", raw: null };
        return {
          formatted: `${m.turnover_rate.toFixed(2)}%`,
          raw: m.turnover_rate,
        };
      }),

      // 策略配置
      buildRow("universe", "策略配置", "回测股票池", "策略运行的标的股票列表", (run) => ({
        formatted: quantUniverseLabel(run),
        raw: null,
      })),
      buildRow("period", "策略配置", "回测区间", "策略运行的历史回测起止时间", (run) => ({
        formatted: `${run.request.start_date} ~ ${run.request.end_date}`,
        raw: null,
      })),
      buildRow("strategy_params", "策略配置", "策略核心参数", "策略运行采用的关键超参数配置", (run) => {
        const strategy = run.request.strategy ?? { type: "ma_cross" };
        const params = strategy.parameters ?? {};
        const entries = Object.entries(params);
        if (entries.length === 0) return { formatted: "默认参数", raw: null };
        const text = entries.map(([k, v]) => `${k}: ${String(v)}`).join(", ");
        return { formatted: text, raw: null };
      }),
    ];
  }, [validRuns]);

  // 生成复制 Markdown 研报
  const handleCopyMarkdown = async () => {
    if (validRuns.length === 0) return;

    const headers = ["指标类别", "衡量指标", ...validRuns.map((r) => `${r.name} (${quantStrategyLabel(r.request.strategy ?? { type: "ma_cross" })})`)];
    const divider = headers.map(() => "---");
    const rows = metricRows.map((row) => [
      row.category,
      row.label,
      ...validRuns.map((r) => String(row.values[r.id] ?? "-")),
    ]);

    const md = [
      `# 策略回测横向对比研报`,
      `生成时间: ${new Date().toLocaleString("zh-CN")}`,
      `对比样本数: ${validRuns.length} 个策略`,
      "",
      `| ${headers.join(" | ")} |`,
      `| ${divider.join(" | ")} |`,
      ...rows.map((r) => `| ${r.join(" | ")} |`),
      "",
      `> 导出自 A-Share Agent 量化投研终端`,
    ].join("\n");

    try {
      await navigator.clipboard.writeText(md);
      setCopied(true);
      void message.success("对比报告已成功复制到剪贴板");
      setTimeout(() => setCopied(false), 2500);
    } catch {
      void message.error("复制失败，请手动选取");
    }
  };

  // 表格列定义
  const columns: ColumnsType<MetricRow> = useMemo(() => {
    const cols: ColumnsType<MetricRow> = [
      {
        title: "指标类别",
        dataIndex: "category",
        key: "category",
        width: 110,
        fixed: "left",
        onCell: (row, index) => {
          if (index == null) return {};
          const prev = metricRows[index - 1];
          if (prev && prev.category === row.category) {
            return { rowSpan: 0 };
          }
          let rowSpan = 1;
          for (let i = index + 1; i < metricRows.length; i++) {
            if (metricRows[i].category === row.category) rowSpan++;
            else break;
          }
          return { rowSpan };
        },
        render: (value: string) => <Tag color="blue">{value}</Tag>,
      },
      {
        title: "衡量指标",
        dataIndex: "label",
        key: "label",
        width: 170,
        fixed: "left",
        render: (label: string, row) => (
          <Tooltip title={row.description} placement="topLeft">
            <span style={{ fontWeight: 600, cursor: "help" }}>{label}</span>
          </Tooltip>
        ),
      },
    ];

    validRuns.forEach((run) => {
      const strategyName = quantStrategyLabel(run.request.strategy ?? { type: "ma_cross" });
      cols.push({
        title: (
          <div style={{ padding: "4px 0", minWidth: 150 }}>
            <div style={{ display: "flex", alignItems: "center", justifyContent: "space-between", gap: 4 }}>
              <Text strong ellipsis style={{ maxWidth: 140 }} title={run.name}>
                {run.name}
              </Text>
              {onRemoveRun && validRuns.length > 2 ? (
                <Button
                  type="text"
                  size="small"
                  icon={<CloseOutlined style={{ fontSize: 11 }} />}
                  aria-label={`移除对比 ${run.name}`}
                  onClick={() => onRemoveRun(run.id)}
                />
              ) : null}
            </div>
            <div style={{ marginTop: 2, display: "flex", gap: 4, flexWrap: "wrap" }}>
              <Tag style={{ fontSize: 11, padding: "0 4px", margin: 0 }}>{strategyName}</Tag>
            </div>
            <div style={{ marginTop: 6 }}>
              <Button
                type="link"
                size="small"
                style={{ padding: 0, fontSize: 12 }}
                onClick={() => {
                  onSelectRun(run.id);
                  onClose();
                }}
              >
                查看此回测 →
              </Button>
            </div>
          </div>
        ),
        dataIndex: run.id,
        key: run.id,
        align: "right",
        render: (_: unknown, row: MetricRow) => {
          const val = row.values[run.id];
          const raw = row.rawValues[run.id];

          // 判断是否本行最优
          let isBest = false;
          if (row.higherIsBetter != null && raw != null) {
            const allRaws = validRuns
              .map((r) => row.rawValues[r.id])
              .filter((v): v is number => typeof v === "number" && !isNaN(v));
            if (allRaws.length > 1) {
              const bestRaw = row.higherIsBetter ? Math.max(...allRaws) : Math.min(...allRaws);
              if (raw === bestRaw) {
                isBest = true;
              }
            }
          }

          // 收益相关颜色区分
          let valueColor: string | undefined;
          if (row.key === "total_return" || row.key === "annualized_return" || row.key === "excess_return") {
            if (raw != null) {
              valueColor = raw >= 0 ? colors.up : colors.down;
            }
          } else if (row.key === "max_drawdown") {
            valueColor = colors.down;
          }

          return (
            <div style={{ display: "inline-flex", alignItems: "center", gap: 6 }}>
              {isBest ? (
                <Badge
                  count={<CrownOutlined style={{ color: "#faad14", fontSize: 13 }} />}
                  title="该项表现最佳"
                />
              ) : null}
              <span
                style={{
                  fontFamily: typeof raw === "number" ? "var(--c-font-mono)" : undefined,
                  fontWeight: isBest ? 700 : 500,
                  color: valueColor,
                  background: isBest ? "rgba(250, 173, 20, 0.08)" : undefined,
                  padding: isBest ? "1px 6px" : undefined,
                  borderRadius: 4,
                }}
              >
                {String(val ?? "-")}
              </span>
            </div>
          );
        },
      });
    });

    return cols;
  }, [validRuns, metricRows, onRemoveRun, onSelectRun, onClose, colors]);

  return (
    <Modal
      open={open}
      title={
        <div style={{ display: "flex", alignItems: "center", gap: 8 }}>
          <FundViewOutlined style={{ color: colors.primary }} />
          <span>策略回测多维横向对比</span>
          <Tag color="cyan">{validRuns.length} 个回测样本</Tag>
        </div>
      }
      width={1000}
      footer={[
        <Button
          key="copy"
          icon={copied ? <CheckCircleOutlined /> : <CopyOutlined />}
          onClick={() => void handleCopyMarkdown()}
        >
          {copied ? "已复制研报" : "复制 Markdown 对比表"}
        </Button>,
        <Button key="close" type="primary" onClick={onClose}>
          完成
        </Button>,
      ]}
      onCancel={onClose}
    >
      {validRuns.length < 2 ? (
        <Empty
          description="请在历史记录中至少勾选 2 个已成功完成的回测任务进行横向对比"
          style={{ padding: "40px 0" }}
        />
      ) : (
        <div style={{ display: "flex", flexDirection: "column", gap: 16, width: "100%" }}>
          {/* 胜出亮点看板 */}
          {highlights ? (
            <div style={{ background: "rgba(0, 0, 0, 0.02)", padding: 12, borderRadius: 8 }}>
              <Row gutter={[12, 12]}>
                {highlights.bestReturn ? (
                  <Col xs={24} sm={12} md={6}>
                    <Card size="small" style={{ borderRadius: 6, borderColor: colors.up }}>
                      <div style={{ display: "flex", alignItems: "center", gap: 6, marginBottom: 4 }}>
                        <TrophyOutlined style={{ color: colors.up }} />
                        <Text strong style={{ fontSize: 12 }}>累计收益冠军</Text>
                      </div>
                      <div style={{ fontSize: 18, fontWeight: 700, color: colors.up, fontFamily: "var(--c-font-mono)" }}>
                        +{highlights.bestReturn.val.toFixed(1)}%
                      </div>
                      <Text type="secondary" ellipsis style={{ fontSize: 11, display: "block" }}>
                        {highlights.bestReturn.run.name}
                      </Text>
                    </Card>
                  </Col>
                ) : null}

                {highlights.bestSharpe ? (
                  <Col xs={24} sm={12} md={6}>
                    <Card size="small" style={{ borderRadius: 6, borderColor: colors.primary }}>
                      <div style={{ display: "flex", alignItems: "center", gap: 6, marginBottom: 4 }}>
                        <CrownOutlined style={{ color: colors.primary }} />
                        <Text strong style={{ fontSize: 12 }}>最优夏普比率</Text>
                      </div>
                      <div style={{ fontSize: 18, fontWeight: 700, color: colors.primary, fontFamily: "var(--c-font-mono)" }}>
                        {highlights.bestSharpe.val.toFixed(2)}
                      </div>
                      <Text type="secondary" ellipsis style={{ fontSize: 11, display: "block" }}>
                        {highlights.bestSharpe.run.name}
                      </Text>
                    </Card>
                  </Col>
                ) : null}

                {highlights.minDrawdown ? (
                  <Col xs={24} sm={12} md={6}>
                    <Card size="small" style={{ borderRadius: 6, borderColor: "#52c41a" }}>
                      <div style={{ display: "flex", alignItems: "center", gap: 6, marginBottom: 4 }}>
                        <SafetyCertificateOutlined style={{ color: "#52c41a" }} />
                        <Text strong style={{ fontSize: 12 }}>最小最大回撤</Text>
                      </div>
                      <div style={{ fontSize: 18, fontWeight: 700, color: "#52c41a", fontFamily: "var(--c-font-mono)" }}>
                        -{highlights.minDrawdown.val.toFixed(1)}%
                      </div>
                      <Text type="secondary" ellipsis style={{ fontSize: 11, display: "block" }}>
                        {highlights.minDrawdown.run.name}
                      </Text>
                    </Card>
                  </Col>
                ) : null}

                {highlights.bestWinRate ? (
                  <Col xs={24} sm={12} md={6}>
                    <Card size="small" style={{ borderRadius: 6, borderColor: "#722ed1" }}>
                      <div style={{ display: "flex", alignItems: "center", gap: 6, marginBottom: 4 }}>
                        <ThunderboltOutlined style={{ color: "#722ed1" }} />
                        <Text strong style={{ fontSize: 12 }}>最高胜率策略</Text>
                      </div>
                      <div style={{ fontSize: 18, fontWeight: 700, color: "#722ed1", fontFamily: "var(--c-font-mono)" }}>
                        {highlights.bestWinRate.val.toFixed(1)}%
                      </div>
                      <Text type="secondary" ellipsis style={{ fontSize: 11, display: "block" }}>
                        {highlights.bestWinRate.run.name}
                      </Text>
                    </Card>
                  </Col>
                ) : null}
              </Row>
            </div>
          ) : null}

          {/* 横向指标对比表格 */}
          <Table<MetricRow>
            columns={columns}
            dataSource={metricRows}
            pagination={false}
            size="small"
            bordered
            scroll={{ x: 280 + validRuns.length * 170, y: 440 }}
          />
        </div>
      )}
    </Modal>
  );
}
