import { useEffect, useMemo, useState } from "react";
import { Link } from "react-router-dom";
import { Button, Card, message, Segmented, Table, Tag, Typography } from "antd";
import { RadarChartOutlined, ThunderboltOutlined } from "@ant-design/icons";
import type { ColumnsType } from "antd/es/table";
import {
  usePotentialDates,
  usePotentialDaily,
  usePotentialPerformance,
  usePotentialRun,
  usePotentialRunStatus,
} from "../../api/queries";
import ChangeValue from "../../components/ChangeValue";
import SectionDataState from "../../components/SectionDataState";
import StockExternalLink from "../../components/StockExternalLink";
import { useColors, useTokens, semanticTagStyle } from "../../styles/ui";
import type { PotentialPerformanceItem, PotentialStockItem } from "../../types/stock";

const { Text } = Typography;

function formatValue(value: number | null | undefined, digits = 2, suffix = "") {
  if (value == null) return "-";
  return `${value.toFixed(digits)}${suffix}`;
}

function regimeLabel(value: string | undefined) {
  if (value === "bull") return "多头";
  if (value === "bear") return "空头";
  return "震荡";
}

function emotionLabel(value: string | undefined) {
  if (value === "strong") return "强";
  if (value === "weak") return "弱";
  return "中";
}

function signalTypeLabel(value: string) {
  const labels: Record<string, string> = {
    trend: "趋势",
    breakout: "突破",
    pullback: "回踩",
    reversal: "反转",
    range: "箱体",
    other: "其他",
  };
  return labels[value] ?? value;
}

export default function PotentialPage() {
  const c = useColors();
  const t = useTokens();
  const datesQuery = usePotentialDates();
  const dates = useMemo(() => datesQuery.data ?? [], [datesQuery.data]);
  const [chosenDate, setChosenDate] = useState<string | null>(null);
  const selectedDate = chosenDate ?? dates[0]?.date ?? null;
  const resultQuery = usePotentialDaily(selectedDate);
  const runMutation = usePotentialRun();
  const [runStarted, setRunStarted] = useState(false);
  const runStatusQuery = usePotentialRunStatus(runStarted);
  const [performanceDays, setPerformanceDays] = useState(5);
  const performanceQuery = usePotentialPerformance(selectedDate, performanceDays);
  const refetchDates = datesQuery.refetch;
  const refetchResult = resultQuery.refetch;
  const runStatus = runStatusQuery.data;

  useEffect(() => {
    if (!runStarted || !runStatus || runStatus.running) {
      return;
    }
    setRunStarted(false);
    void refetchDates();
    void refetchResult();
    if (runStatus.status === "failed") {
      message.error(`挖掘失败：${runStatus.error ?? "未知错误"}`);
    } else {
      message.success(`挖掘完成${runStatus.date ? `：${runStatus.date}` : ""}`);
    }
  }, [runStarted, runStatus, refetchDates, refetchResult]);

  const items = useMemo(() => resultQuery.data?.items ?? [], [resultQuery.data?.items]);

  const isLatestDate = selectedDate == null || selectedDate === dates[0]?.date;

  const columns: ColumnsType<PotentialStockItem> = useMemo(() => [
    {
      title: "#",
      key: "rank",
      width: 52,
      align: "center",
      render: (_: unknown, __: PotentialStockItem, index: number) => {
        let rankBg = c.nestedBg;
        let rankColor = c.textSecondary;
        if (index === 0) {
          rankBg = "linear-gradient(135deg, #ffd700, #ffaa00)";
          rankColor = "#7a4100";
        } else if (index === 1) {
          rankBg = "linear-gradient(135deg, #e0e0e0, #b0bec5)";
          rankColor = "#37474f";
        } else if (index === 2) {
          rankBg = "linear-gradient(135deg, #ffcc80, #d7ccc8)";
          rankColor = "#5d4037";
        }
        return (
          <span
            style={{
              display: "inline-flex", alignItems: "center", justifyContent: "center",
              width: 24, height: 24, borderRadius: t.radius.sm,
              fontSize: t.font.xs, fontWeight: Number(t.weight.bold),
              color: rankColor,
              background: rankBg,
              boxShadow: index < 3 ? "0 2px 6px rgba(0,0,0,0.12)" : undefined,
            }}
          >
            {index + 1}
          </span>
        );
      },
    },
    {
      title: "股票",
      key: "stock",
      width: 160,
      render: (_: unknown, record: PotentialStockItem) => (
        <StockExternalLink code={record.code} name={record.name} style={{ color: c.primary, display: "flex", flexDirection: "column", minWidth: 0 }}>
          <span style={{ color: c.textPrimary, fontWeight: Number(t.weight.semibold) }}>{record.name}</span>
          <span style={{ color: c.textMuted, fontSize: t.font.xs }}>{record.code}</span>
        </StockExternalLink>
      ),
    },
    {
      title: isLatestDate ? "收盘价" : "选出收盘价",
      dataIndex: "price",
      width: 100,
      align: "right",
      render: (value: number | null) => formatValue(value),
    },
    {
      title: isLatestDate ? "涨跌幅" : "当日涨跌",
      dataIndex: "change_pct",
      width: 90,
      align: "right",
      render: (value: number | null) => <ChangeValue value={value} fontWeight={Number(t.weight.medium)} />,
    },
    {
      title: "行业",
      dataIndex: "industry",
      width: 100,
      render: (value: string | null) => (
        value ? <Tag style={{ ...semanticTagStyle("info"), fontSize: t.font.xs }}>{value}</Tag> : <span style={{ color: c.textMuted }}>-</span>
      ),
    },
    {
      title: "综合评分",
      dataIndex: "score",
      width: 100,
      align: "right",
      sorter: (a: PotentialStockItem, b: PotentialStockItem) => a.score - b.score,
      render: (value: number) => {
        const isHigh = value >= 4.5;
        return (
          <span
            className={isHigh ? "potential-score-badge--high" : "potential-score-badge"}
            style={{
              fontWeight: Number(t.weight.bold),
              color: isHigh ? c.accent : c.primary,
              fontFamily: "var(--c-font-mono)",
            }}
          >
            {value.toFixed(1)}
          </span>
        );
      },
    },
    {
      title: "质量分",
      dataIndex: "quality_score",
      width: 84,
      align: "right",
      sorter: (a: PotentialStockItem, b: PotentialStockItem) => a.quality_score - b.quality_score,
      render: (value: number) => (
        <span style={{ color: value < 0 ? c.warning : c.textSecondary, fontFamily: "var(--c-font-mono)" }}>
          {value.toFixed(1)}
        </span>
      ),
    },
    {
      title: "命中策略",
      dataIndex: "strategies",
      render: (strategies: string[]) => (
        <span style={{ display: "flex", flexWrap: "wrap", gap: t.space[1] }}>
          {strategies.map((name) => (
            <Tag key={name} style={{ ...semanticTagStyle("primary"), fontSize: t.font.xs, marginInlineEnd: 0 }}>{name}</Tag>
          ))}
        </span>
      ),
    },
    {
      title: "信号日期",
      dataIndex: "signal_date",
      width: 110,
      render: (value: string, record: PotentialStockItem) => (
        <span style={{ fontFamily: "var(--c-font-mono)" }}>
          {value || "-"}
          {record.signal_age_days != null && record.signal_age_days <= 3 ? (
            <Tag
              className="potential-signal-new-tag"
              style={{
                ...semanticTagStyle("up"),
                fontSize: t.font.xs,
                marginInlineStart: t.space[1],
                fontWeight: Number(t.weight.semibold),
              }}
            >
              新
            </Tag>
          ) : null}
        </span>
      ),
    },
    {
      title: "成交额(亿)",
      dataIndex: "amount",
      width: 100,
      align: "right",
      render: (value: number | null) => formatValue(value),
    },
  ], [c, t, isLatestDate]);

  const performanceColumns: ColumnsType<PotentialPerformanceItem> = useMemo(() => [
    {
      title: "股票",
      key: "stock",
      render: (_: unknown, record: PotentialPerformanceItem) => (
        <StockExternalLink code={record.code} name={record.name} style={{ color: c.primary, display: "flex", flexDirection: "column" }}>
          <span style={{ color: c.textPrimary, fontWeight: Number(t.weight.semibold) }}>{record.name}</span>
          <span style={{ color: c.textMuted, fontSize: t.font.xs }}>{record.code}</span>
        </StockExternalLink>
      ),
    },
    {
      title: "行业",
      dataIndex: "industry",
      width: 100,
      render: (value: string | null) => value ? <Tag style={{ ...semanticTagStyle("info"), fontSize: t.font.xs }}>{value}</Tag> : "-",
    },
    {
      title: "买入价",
      dataIndex: "entry_price",
      width: 90,
      align: "right",
      render: (value: number | null) => formatValue(value),
    },
    {
      title: "期末价",
      dataIndex: "exit_price",
      width: 90,
      align: "right",
      render: (value: number | null) => formatValue(value),
    },
    {
      title: "区间收益",
      dataIndex: "return_pct",
      width: 100,
      align: "right",
      render: (value: number | null) => <ChangeValue value={value} />,
    },
    {
      title: "超额收益",
      dataIndex: "excess_return_pct",
      width: 100,
      align: "right",
      render: (value: number | null) => <ChangeValue value={value} />,
    },
    {
      title: "最大浮盈",
      dataIndex: "max_return_pct",
      width: 100,
      align: "right",
      render: (value: number | null) => <ChangeValue value={value} />,
    },
    {
      title: "最大回撤",
      dataIndex: "max_drawdown_pct",
      width: 100,
      align: "right",
      render: (value: number | null) => <ChangeValue value={value} />,
    },
  ], [c, t]);

  return (
    <div aria-label="潜力股挖掘页">
      <Card
        title={(
          <span style={{ display: "inline-flex", alignItems: "center", gap: t.space[2] }}>
            <RadarChartOutlined style={{ color: c.primary }} />
            <span>每日潜力股</span>
            <Tag
              style={{
                fontFamily: "var(--c-font-mono)",
                fontSize: t.font.xs,
                color: c.primary,
                borderColor: "color-mix(in srgb, var(--c-primary) 35%, transparent)",
                background: "color-mix(in srgb, var(--c-primary) 10%, transparent)",
                letterSpacing: "0.06em",
              }}
            >
              QUANT RADAR
            </Tag>
          </span>
        )}
        extra={(
          <Button
            icon={<ThunderboltOutlined />}
            loading={runMutation.isPending || runStarted}
            onClick={() => runMutation.mutate(false, {
              onSuccess: () => {
                setRunStarted(true);
                message.info("已开始后台挖掘，完成后自动刷新");
              },
              onError: (error: unknown) => {
                message.error(`触发失败：${error instanceof Error ? error.message : String(error)}`);
              },
            })}
          >
            {runStarted ? "挖掘中" : "立即挖掘"}
          </Button>
        )}
      >
        <div style={{ display: "flex", flexWrap: "wrap", justifyContent: "space-between", gap: t.space[2], marginBottom: t.space[3] }}>
          <Segmented
            aria-label="结果日期"
            value={selectedDate ?? undefined}
            options={dates.slice(0, 7).map((item) => ({ label: item.date.slice(5), value: item.date }))}
            onChange={(value) => setChosenDate(String(value))}
          />
          {resultQuery.data ? (
            <div style={{ display: "flex", flexWrap: "wrap", alignItems: "center", gap: t.space[2] }}>
              <Tag
                style={{
                  ...semanticTagStyle(
                    resultQuery.data.market_regime === "bull"
                      ? "up"
                      : resultQuery.data.market_regime === "bear"
                        ? "down"
                        : "info",
                  ),
                  margin: 0,
                }}
              >
                市场{regimeLabel(resultQuery.data.market_regime)}
              </Tag>
              <Tag
                style={{
                  ...semanticTagStyle(
                    resultQuery.data.market_emotion === "strong"
                      ? "up"
                      : resultQuery.data.market_emotion === "weak"
                        ? "down"
                        : "info",
                  ),
                  margin: 0,
                }}
              >
                情绪{emotionLabel(resultQuery.data.market_emotion)}
              </Tag>
              {resultQuery.data.market_note ? (
                <Text type="secondary" style={{ fontSize: t.font.xs }}>{resultQuery.data.market_note}</Text>
              ) : null}
              {(resultQuery.data.hot_themes ?? []).slice(0, 5).map((theme) => (
                <Tag key={theme} style={{ ...semanticTagStyle("accent"), margin: 0, fontSize: t.font.xs }}>{theme}</Tag>
              ))}
              <Text type="secondary" style={{ fontSize: t.font.sm }}>
                {resultQuery.data.date} 生成 · 候选池 {resultQuery.data.universe_size} 只 · 评估 {resultQuery.data.evaluated} 只 · 命中 {items.length} 只
              </Text>
            </div>
          ) : null}
        </div>
        <SectionDataState
          isLoading={resultQuery.isLoading}
          error={resultQuery.error}
          onRetry={() => resultQuery.refetch()}
          isEmpty={!resultQuery.isLoading && !resultQuery.error && items.length === 0}
          emptyText="暂无潜力股结果，可点击右上角「立即挖掘」生成今日结果（后台也会在每日收盘后自动运行）"
          errorTitle="潜力股数据加载失败"
          skeletonRows={8}
          minHeight={320}
        >
          <Table<PotentialStockItem>
            columns={columns}
            dataSource={items}
            rowKey={(record) => `${record.code}-${record.score}`}
            size="small"
            pagination={{ pageSize: 20, showSizeChanger: false }}
            scroll={{ x: "max-content" }}
            expandable={{
              expandedRowRender: (record) => (
                <div style={{ display: "grid", gap: t.space[2], padding: `${t.space[1]} 0` }}>
                  <Text style={{ color: c.textSecondary }}>{record.reason || "暂无入选说明"}</Text>
                  <div style={{ display: "flex", flexWrap: "wrap", gap: t.space[1] }}>
                    <Tag style={{ ...semanticTagStyle("primary"), margin: 0 }}>信号分 {record.signal_score.toFixed(1)}</Tag>
                    <Tag style={{ ...semanticTagStyle("info"), margin: 0 }}>质量分 {record.quality_score.toFixed(1)}</Tag>
                    <Tag style={{ ...semanticTagStyle("accent"), margin: 0 }}>基本面分 {record.fundamental_score.toFixed(1)}</Tag>
                    {record.theme_score > 0 ? (
                      <Tag style={{ ...semanticTagStyle("warning"), margin: 0 }}>题材分 {record.theme_score.toFixed(1)}</Tag>
                    ) : null}
                    {record.sector_strength != null ? (
                      <Tag style={{ ...semanticTagStyle("info"), margin: 0 }}>行业中位 {record.sector_strength.toFixed(1)}%</Tag>
                    ) : null}
                    {record.signal_types.map((type) => (
                      <Tag key={type} style={{ ...semanticTagStyle("accent"), margin: 0 }}>{signalTypeLabel(type)}</Tag>
                    ))}
                    {(record.themes ?? []).map((theme) => (
                      <Tag key={theme} style={{ ...semanticTagStyle("warning"), margin: 0 }}>{theme}</Tag>
                    ))}
                  </div>
                  {record.risk_flags.length > 0 ? (
                    <div style={{ display: "flex", flexWrap: "wrap", gap: t.space[1] }}>
                      {record.risk_flags.map((flag) => (
                        <Tag key={flag} style={{ ...semanticTagStyle("warning"), margin: 0 }}>{flag}</Tag>
                      ))}
                    </div>
                  ) : null}
                </div>
              ),
              rowExpandable: (record) => Boolean(record.reason || record.risk_flags?.length || record.signal_types?.length),
            }}
          />
        </SectionDataState>
        <Text type="secondary" style={{ fontSize: t.font.xs }}>
          说明：候选池按成交额/活跃度/估值质量三层筛选，并剔除 ST/次新/低流动性标的；评分 = 策略信号分（策略族封顶、信号时效衰减、市场环境加权）
          + 质量分（趋势/量能/估值/行业强弱/风险扣分）+ 基本面分（ROE/增长/负债/现金流）+ 题材分（当日热门题材/行业），输出按行业分散。仅供研究参考，不构成投资建议。股票名称可点击进入
          <Link to="/screener" style={{ color: c.primary }}>选股器</Link>
          进一步筛选或查看个股分析。
        </Text>
      </Card>
      <Card
        size="small"
        title="历史表现复盘"
        style={{ marginTop: t.space[4] }}
        extra={(
          <Segmented
            size="small"
            value={performanceDays}
            options={[5, 10, 20].map((days) => ({ label: `${days}日`, value: days }))}
            onChange={(value) => setPerformanceDays(Number(value))}
          />
        )}
      >
        {performanceQuery.isLoading ? (
          <Text type="secondary">加载中...</Text>
        ) : performanceQuery.error ? (
          <Text type="danger">历史表现数据加载失败</Text>
        ) : performanceQuery.data ? (
          performanceQuery.data.evaluated_count > 0 ? (
            <div style={{ display: "grid", gap: t.space[3] }}>
              <div style={{ display: "grid", gridTemplateColumns: "repeat(auto-fit, minmax(120px, 1fr))", gap: t.space[2] }}>
                <div style={{ background: c.nestedBg, borderRadius: t.radius.md, padding: t.space[3], textAlign: "center" }}>
                  <div style={{ color: c.textSecondary, fontSize: t.font.xs }}>胜率</div>
                  <div style={{ color: c.textPrimary, fontWeight: Number(t.weight.bold), fontFamily: "var(--c-font-mono)" }}>
                    {performanceQuery.data.win_rate != null ? `${(performanceQuery.data.win_rate * 100).toFixed(0)}%` : "-"}
                  </div>
                </div>
                <div style={{ background: c.nestedBg, borderRadius: t.radius.md, padding: t.space[3], textAlign: "center" }}>
                  <div style={{ color: c.textSecondary, fontSize: t.font.xs }}>平均收益</div>
                  <div style={{ fontWeight: Number(t.weight.bold) }}><ChangeValue value={performanceQuery.data.average_return_pct} /></div>
                </div>
                <div style={{ background: c.nestedBg, borderRadius: t.radius.md, padding: t.space[3], textAlign: "center" }}>
                  <div style={{ color: c.textSecondary, fontSize: t.font.xs }}>中位收益</div>
                  <div style={{ fontWeight: Number(t.weight.bold) }}><ChangeValue value={performanceQuery.data.median_return_pct} /></div>
                </div>
                <div style={{ background: c.nestedBg, borderRadius: t.radius.md, padding: t.space[3], textAlign: "center" }}>
                  <div style={{ color: c.textSecondary, fontSize: t.font.xs }}>平均超额</div>
                  <div style={{ fontWeight: Number(t.weight.bold) }}><ChangeValue value={performanceQuery.data.average_excess_pct} /></div>
                </div>
                <div style={{ background: c.nestedBg, borderRadius: t.radius.md, padding: t.space[3], textAlign: "center" }}>
                  <div style={{ color: c.textSecondary, fontSize: t.font.xs }}>沪深300</div>
                  <div style={{ fontWeight: Number(t.weight.bold) }}><ChangeValue value={performanceQuery.data.benchmark_return_pct} /></div>
                </div>
              </div>
              <Text type="secondary" style={{ fontSize: t.font.xs }}>
                已评估 {performanceQuery.data.evaluated_count}/{performanceQuery.data.item_count} 只 · 持有 {performanceQuery.data.days} 个交易日
              </Text>
              <Table<PotentialPerformanceItem>
                columns={performanceColumns}
                dataSource={performanceQuery.data.items}
                rowKey={(record) => record.code}
                size="small"
                pagination={false}
                scroll={{ x: "max-content" }}
              />
              {performanceQuery.data.message ? (
                <Text type="secondary" style={{ fontSize: t.font.xs }}>{performanceQuery.data.message}</Text>
              ) : null}
            </div>
          ) : (
            <Text type="secondary">{performanceQuery.data.message ?? "暂无足够的前瞻数据"}</Text>
          )
        ) : (
          <Text type="secondary">暂无历史表现数据</Text>
        )}
      </Card>
    </div>
  );
}
