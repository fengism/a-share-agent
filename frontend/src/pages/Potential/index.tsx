import { useCallback, useEffect, useMemo, useState } from "react";
import { Link, useNavigate } from "react-router-dom";
import { Button, Card, message, Segmented, Table, Tag, Tooltip, Typography } from "antd";
import {
  FireOutlined,
  LineChartOutlined,
  RadarChartOutlined,
  RobotOutlined,
  StarFilled,
  StarOutlined,
  ThunderboltOutlined,
} from "@ant-design/icons";
import type { ColumnsType } from "antd/es/table";
import {
  usePotentialDates,
  usePotentialDaily,
  usePotentialPerformance,
  usePotentialRun,
  usePotentialRunStatus,
  useWatchlist,
  useAddWatchlistItem,
  useDeleteWatchlistItem,
} from "../../api/queries";
import ChangeValue from "../../components/ChangeValue";
import SectionDataState from "../../components/SectionDataState";
import StateTrajectoryBadge from "../../components/StateTrajectoryBadge";
import StockExternalLink from "../../components/StockExternalLink";
import StockWorkspaceDrawer from "../../components/StockWorkspaceDrawer";
import { useColors, useTokens, semanticTagStyle } from "../../styles/ui";
import type { PotentialPerformanceItem, PotentialStockItem } from "../../types/stock";
import { triggerStockAiDiagnosis } from "../../utils/copilotEvents";
import "./styles/index.css";

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

function getCategoryMeta(category?: string, categoryLabel?: string) {
  switch (category) {
    case "anchor":
      return {
        label: categoryLabel || "机构中军",
        icon: "🛡️",
        className: "potential-category--anchor",
      };
    case "reversal":
      return {
        label: categoryLabel || "超跌反转",
        icon: "💎",
        className: "potential-category--reversal",
      };
    case "quality":
      return {
        label: categoryLabel || "价值优选",
        icon: "⭐",
        className: "potential-category--quality",
      };
    case "pioneer":
    default:
      return {
        label: categoryLabel || "趋势先锋",
        icon: "🏹",
        className: "potential-category--pioneer",
      };
  }
}

export default function PotentialPage() {
  const c = useColors();
  const t = useTokens();
  const navigate = useNavigate();
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

  // Watchlist integration
  const { data: watchlistData } = useWatchlist();
  const addWatchlistMutation = useAddWatchlistItem();
  const deleteWatchlistMutation = useDeleteWatchlistItem();
  const watchlistCodes = useMemo(() => {
    return new Set((watchlistData?.items ?? []).map((item) => item.stock_code));
  }, [watchlistData]);

  const handleToggleWatchlist = useCallback((record: { code: string; name: string }) => {
    if (watchlistCodes.has(record.code)) {
      deleteWatchlistMutation.mutate(record.code, {
        onSuccess: () => message.success(`已从自选移除 ${record.name}`),
        onError: (err: unknown) => message.error(`移除自选失败：${err instanceof Error ? err.message : String(err)}`),
      });
    } else {
      addWatchlistMutation.mutate({ stock_code: record.code, note: record.name }, {
        onSuccess: () => message.success(`已添加 ${record.name} 到自选`),
        onError: (err: unknown) => message.error(`添加自选失败：${err instanceof Error ? err.message : String(err)}`),
      });
    }
  }, [watchlistCodes, deleteWatchlistMutation, addWatchlistMutation]);

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

  const topPicks = useMemo(() => {
    if (resultQuery.data?.top_picks && resultQuery.data.top_picks.length > 0) {
      return resultQuery.data.top_picks;
    }
    return items.slice(0, 3);
  }, [resultQuery.data?.top_picks, items]);

  const [previewStock, setPreviewStock] = useState<{ code: string; name: string } | null>(null);
  const [intentFilter, setIntentFilter] = useState<string>("ALL");

  const { filteredItems, counts } = useMemo(() => {
    let pioneer = 0;
    let anchor = 0;
    let reversal = 0;
    let quality = 0;
    let risk = 0;

    items.forEach((item) => {
      const isPioneer = item.category === "pioneer" || item.signal_types?.includes("breakout") || item.strategies?.some((s) => s.includes("突破"));
      const isAnchor = item.category === "anchor" || (item.market_cap != null && item.market_cap >= 300 && (item.signal_types?.includes("trend") || item.strategies?.some((s) => s.includes("趋势"))));
      const isReversal = item.category === "reversal" || item.signal_types?.includes("reversal") || item.strategies?.some((s) => s.includes("底部") || s.includes("反转"));
      const isQuality = item.category === "quality" || item.quality_score >= 1.0 || item.fundamental_score >= 1.0;
      const isRisk = Boolean(item.risk_flags && item.risk_flags.length > 0);

      if (isPioneer) pioneer += 1;
      if (isAnchor) anchor += 1;
      if (isReversal) reversal += 1;
      if (isQuality) quality += 1;
      if (isRisk) risk += 1;
    });

    const filtered = items.filter((item) => {
      if (intentFilter === "ALL") return true;
      if (intentFilter === "pioneer") {
        return item.category === "pioneer" || item.signal_types?.includes("breakout") || item.strategies?.some((s) => s.includes("突破"));
      }
      if (intentFilter === "anchor") {
        return item.category === "anchor" || (item.market_cap != null && item.market_cap >= 300 && (item.signal_types?.includes("trend") || item.strategies?.some((s) => s.includes("趋势"))));
      }
      if (intentFilter === "reversal") {
        return item.category === "reversal" || item.signal_types?.includes("reversal") || item.strategies?.some((s) => s.includes("底部") || s.includes("反转"));
      }
      if (intentFilter === "quality") {
        return item.category === "quality" || item.quality_score >= 1.0 || item.fundamental_score >= 1.0;
      }
      if (intentFilter === "risk") {
        return Boolean(item.risk_flags && item.risk_flags.length > 0);
      }
      return true;
    });

    return {
      filteredItems: filtered,
      counts: { pioneer, anchor, reversal, quality, risk },
    };
  }, [items, intentFilter]);

  const isLatestDate = selectedDate == null || selectedDate === dates[0]?.date;

  const columns: ColumnsType<PotentialStockItem> = useMemo(() => [
    {
      title: "#",
      key: "rank",
      width: 48,
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
      title: "风格",
      key: "category",
      width: 96,
      render: (_: unknown, record: PotentialStockItem) => {
        const meta = getCategoryMeta(record.category, record.category_label);
        return (
          <Tag className={`potential-category ${meta.className} potential-category--medium`}>
            {meta.icon} {meta.label}
          </Tag>
        );
      },
    },
    {
      title: "股票",
      key: "stock",
      width: 140,
      render: (_: unknown, record: PotentialStockItem) => (
        <StockExternalLink code={record.code} name={record.name} style={{ color: c.primary, display: "flex", flexDirection: "column", minWidth: 0 }}>
          <span className="potential-text-primary u-text-semibold">{record.name}</span>
          <span className="u-text-muted u-text-xs">{record.code}</span>
        </StockExternalLink>
      ),
    },
    {
      title: isLatestDate ? "收盘价" : "选出收盘价",
      dataIndex: "price",
      width: 90,
      align: "right",
      render: (value: number | null) => formatValue(value),
    },
    {
      title: isLatestDate ? "涨跌幅" : "当日涨跌",
      dataIndex: "change_pct",
      width: 85,
      align: "right",
      render: (value: number | null) => <ChangeValue value={value} fontWeight={Number(t.weight.medium)} />,
    },
    {
      title: "行业",
      dataIndex: "industry",
      width: 95,
      render: (value: string | null) => (
        value ? <Tag style={{ ...semanticTagStyle("info"), fontSize: t.font.xs }}>{value}</Tag> : <span className="u-text-muted">-</span>
      ),
    },
    {
      title: "形态轨迹",
      key: "trajectory",
      width: 150,
      render: (_: unknown, record: PotentialStockItem) => (
        <StateTrajectoryBadge
          signalTypes={record.signal_types}
          strategies={record.strategies}
        />
      ),
    },
    {
      title: "综合评分",
      dataIndex: "score",
      width: 90,
      align: "right",
      sorter: (a: PotentialStockItem, b: PotentialStockItem) => a.score - b.score,
      render: (value: number, record: PotentialStockItem) => {
        const isHigh = value >= 4.5;
        const tooltipContent = (
          <div style={{ display: "grid", gap: 4, fontSize: t.font.xs, minWidth: 150 }}>
            <div style={{ fontWeight: Number(t.weight.bold), borderBottom: `1px solid ${c.border}`, paddingBottom: 2 }}>
              评分明细拆解 (总分: {value.toFixed(1)})
            </div>
            <div className="potential-row-split">
              <span className="u-text-secondary">策略信号分:</span>
              <span className="potential-mono-semibold">+{record.signal_score.toFixed(1)}</span>
            </div>
            <div className="potential-row-split">
              <span className="u-text-secondary">技术质量分:</span>
              <span style={{ fontWeight: Number(t.weight.semibold), fontFamily: "var(--c-font-mono)", color: record.quality_score < 0 ? c.warning : undefined }}>
                {record.quality_score >= 0 ? `+${record.quality_score.toFixed(1)}` : record.quality_score.toFixed(1)}
              </span>
            </div>
            <div className="potential-row-split">
              <span className="u-text-secondary">基本面分:</span>
              <span className="potential-mono-semibold">+{record.fundamental_score.toFixed(1)}</span>
            </div>
            {record.theme_score > 0 ? (
              <div className="potential-row-split">
                <span className="u-text-secondary">热门题材分:</span>
                <span style={{ fontWeight: Number(t.weight.semibold), fontFamily: "var(--c-font-mono)", color: c.accent }}>+{record.theme_score.toFixed(1)}</span>
              </div>
            ) : null}
            {record.sector_strength != null ? (
              <div style={{ display: "flex", justifyContent: "space-between", color: c.textMuted }}>
                <span>行业中位强度:</span>
                <span>{record.sector_strength.toFixed(1)}%</span>
              </div>
            ) : null}
          </div>
        );
        return (
          <Tooltip title={tooltipContent} placement="topRight">
            <span
              className={isHigh ? "potential-score-badge--high" : "potential-score-badge"}
              style={{
                fontWeight: Number(t.weight.bold),
                color: isHigh ? c.accent : c.primary,
                fontFamily: "var(--c-font-mono)",
                cursor: "help",
                borderBottom: "1px dashed currentColor",
              }}
            >
              {value.toFixed(1)}
            </span>
          </Tooltip>
        );
      },
    },
    {
      title: "命中策略",
      dataIndex: "strategies",
      render: (strategies: string[]) => (
        <span className="potential-tags-row">
          {strategies.map((name) => (
            <Tag key={name} style={{ ...semanticTagStyle("primary"), fontSize: t.font.xs, marginInlineEnd: 0 }}>{name}</Tag>
          ))}
        </span>
      ),
    },
    {
      title: "信号日期",
      dataIndex: "signal_date",
      width: 105,
      render: (value: string, record: PotentialStockItem) => (
        <span className="u-font-mono">
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
      width: 90,
      align: "right",
      render: (value: number | null) => formatValue(value),
    },
    {
      title: "快捷操作",
      key: "actions",
      width: 110,
      align: "center",
      render: (_: unknown, record: PotentialStockItem) => {
        const isFavorited = watchlistCodes.has(record.code);
        return (
          <div className="potential-center-row">
            <Button
              type="text"
              size="small"
              icon={isFavorited ? <StarFilled style={{ color: "#faad14" }} /> : <StarOutlined />}
              title={isFavorited ? "从自选移除" : "加入自选"}
              aria-label={`${isFavorited ? "移除" : "加入"} ${record.name} 自选`}
              onClick={(e) => {
                e.preventDefault();
                e.stopPropagation();
                handleToggleWatchlist(record);
              }}
            />
            <Button
              type="text"
              size="small"
              icon={<LineChartOutlined />}
              title="K线速查"
              aria-label={`速查 ${record.name} K线`}
              onClick={(e) => {
                e.preventDefault();
                e.stopPropagation();
                setPreviewStock({ code: record.code, name: record.name });
              }}
            />
            <Button
              type="text"
              size="small"
              icon={<RobotOutlined className="u-text-primary" />}
              title="AI 深度诊断"
              aria-label={`AI诊断 ${record.name}`}
              onClick={(e) => {
                e.preventDefault();
                e.stopPropagation();
                triggerStockAiDiagnosis(record.code, record.name, navigate);
              }}
            />
          </div>
        );
      },
    },
  ], [c, t, isLatestDate, watchlistCodes, navigate, handleToggleWatchlist]);

  const performanceColumns: ColumnsType<PotentialPerformanceItem> = useMemo(() => [
    {
      title: "股票",
      key: "stock",
      render: (_: unknown, record: PotentialPerformanceItem) => (
        <StockExternalLink code={record.code} name={record.name} style={{ color: c.primary, display: "flex", flexDirection: "column" }}>
          <span className="potential-text-primary u-text-semibold">{record.name}</span>
          <span className="u-text-muted u-text-xs">{record.code}</span>
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
          <span className="potential-inline-center">
            <RadarChartOutlined className="u-text-primary" />
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
        <div className="potential-toolbar">
          <Segmented
            aria-label="结果日期"
            value={selectedDate ?? undefined}
            options={dates.slice(0, 7).map((item) => ({ label: item.date.slice(5), value: item.date }))}
            onChange={(value) => setChosenDate(String(value))}
          />
          {resultQuery.data ? (
            <div className="potential-wrap-row">
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
                <Text type="secondary" className="u-text-xs">{resultQuery.data.market_note}</Text>
              ) : null}
              {(resultQuery.data.hot_themes ?? []).slice(0, 5).map((theme) => (
                <Tag key={theme} style={{ ...semanticTagStyle("accent"), margin: 0, fontSize: t.font.xs }}>{theme}</Tag>
              ))}
              <Text type="secondary" className="u-text-sm">
                {resultQuery.data.date} 生成 · 候选池 {resultQuery.data.universe_size} 只 · 评估 {resultQuery.data.evaluated} 只 · 命中 {items.length} 只
              </Text>
            </div>
          ) : null}
        </div>

        {/* 今日三大精选金股高光看板 */}
        {topPicks.length > 0 ? (
          <div className="u-mb-16">
            <div className="potential-row-between">
              <div className="potential-inline-tight">
                <FireOutlined style={{ color: "#fa541c", fontSize: 16 }} />
                <span style={{ fontWeight: Number(t.weight.bold), fontSize: t.font.sm, color: c.textPrimary }}>
                  今日精选金股
                </span>
                <Tag style={{ ...semanticTagStyle("accent"), fontSize: t.font.xs, margin: 0 }}>
                  Top Picks
                </Tag>
              </div>
              <Text type="secondary" className="u-text-xs">
                多头共振、安全边际与题材热度综合遴选核心标的
              </Text>
            </div>
            <div
              style={{
                display: "grid",
                gridTemplateColumns: "repeat(auto-fit, minmax(280px, 1fr))",
                gap: t.space[3],
              }}
            >
              {topPicks.map((pick) => {
                const meta = getCategoryMeta(pick.category, pick.category_label);
                const isFavorited = watchlistCodes.has(pick.code);
                return (
                  <div
                    key={pick.code}
                    style={{
                      background: c.nestedBg,
                      borderRadius: t.radius.lg,
                      border: `1px solid ${c.border}`,
                      padding: `${t.space[3]}px ${t.space[3]}px`,
                      display: "flex",
                      flexDirection: "column",
                      justifyContent: "space-between",
                      gap: t.space[2],
                      position: "relative",
                    }}
                  >
                    <div>
                      {/* Header */}
                      <div className="potential-row-between">
                        <div style={{ display: "flex", alignItems: "center", gap: 6 }}>
                          <Tag className={`potential-category ${meta.className}`}>
                            {meta.icon} {meta.label}
                          </Tag>
                          {pick.industry ? (
                            <Tag style={{ ...semanticTagStyle("info"), fontSize: t.font.xs, margin: 0 }}>
                              {pick.industry}
                            </Tag>
                          ) : null}
                        </div>
                        <span
                          style={{
                            fontFamily: "var(--c-font-mono)",
                            fontWeight: Number(t.weight.bold),
                            fontSize: t.font.sm,
                            color: pick.score >= 4.5 ? c.accent : c.primary,
                          }}
                        >
                          综合 {pick.score.toFixed(1)}
                        </span>
                      </div>

                      {/* Stock Main */}
                      <div style={{ display: "flex", alignItems: "baseline", justifyContent: "space-between", marginBottom: t.space[2] }}>
                        <div>
                          <StockExternalLink code={pick.code} name={pick.name} style={{ display: "inline-flex", alignItems: "baseline", gap: 6 }}>
                            <span style={{ fontSize: t.font.md, fontWeight: Number(t.weight.bold), color: c.textPrimary }}>
                              {pick.name}
                            </span>
                            <span style={{ fontSize: t.font.xs, color: c.textMuted }}>
                              {pick.code}
                            </span>
                          </StockExternalLink>
                        </div>
                        <div style={{ textAlign: "right" }}>
                          <span style={{ fontFamily: "var(--c-font-mono)", fontWeight: Number(t.weight.semibold), fontSize: t.font.md, marginRight: 6 }}>
                            {formatValue(pick.price)}
                          </span>
                          <ChangeValue value={pick.change_pct} fontWeight={Number(t.weight.bold)} />
                        </div>
                      </div>

                      {/* 4-Dim Mini Scores */}
                      <div
                        style={{
                          display: "grid",
                          gridTemplateColumns: "repeat(4, 1fr)",
                          gap: 4,
                          background: c.cardBg,
                          borderRadius: t.radius.sm,
                          padding: "4px 8px",
                          fontSize: t.font.xs,
                          textAlign: "center",
                          marginBottom: t.space[2],
                        }}
                      >
                        <div>
                          <div className="u-text-muted">信号</div>
                          <div className="potential-mono-semibold">
                            {pick.signal_score.toFixed(1)}
                          </div>
                        </div>
                        <div>
                          <div className="u-text-muted">质量</div>
                          <div style={{ fontWeight: Number(t.weight.semibold), fontFamily: "var(--c-font-mono)", color: pick.quality_score < 0 ? c.warning : undefined }}>
                            {pick.quality_score.toFixed(1)}
                          </div>
                        </div>
                        <div>
                          <div className="u-text-muted">基本面</div>
                          <div className="potential-mono-semibold">
                            {pick.fundamental_score.toFixed(1)}
                          </div>
                        </div>
                        <div>
                          <div className="u-text-muted">题材</div>
                          <div style={{ fontWeight: Number(t.weight.semibold), fontFamily: "var(--c-font-mono)", color: pick.theme_score > 0 ? c.accent : undefined }}>
                            {pick.theme_score.toFixed(1)}
                          </div>
                        </div>
                      </div>

                      {/* Reason */}
                      <div
                        style={{
                          fontSize: t.font.xs,
                          color: c.textSecondary,
                          lineHeight: 1.4,
                          display: "-webkit-box",
                          WebkitLineClamp: 2,
                          WebkitBoxOrient: "vertical",
                          overflow: "hidden",
                          textOverflow: "ellipsis",
                          minHeight: 34,
                        }}
                        title={pick.reason}
                      >
                        {pick.reason || "符合多维量化筛选模型"}
                      </div>
                    </div>

                    {/* Action Bar */}
                    <div
                      style={{
                        display: "flex",
                        alignItems: "center",
                        justifyContent: "space-between",
                        gap: 8,
                        marginTop: t.space[2],
                        paddingTop: t.space[2],
                        borderTop: `1px dashed ${c.border}`,
                      }}
                    >
                      <Button
                        type="primary"
                        ghost
                        size="small"
                        icon={<RobotOutlined />}
                        style={{ flex: 1 }}
                        onClick={() => triggerStockAiDiagnosis(pick.code, pick.name, navigate)}
                      >
                        AI诊断
                      </Button>
                      <Button
                        size="small"
                        icon={<LineChartOutlined />}
                        onClick={() => setPreviewStock({ code: pick.code, name: pick.name })}
                      >
                        K线
                      </Button>
                      <Button
                        size="small"
                        icon={isFavorited ? <StarFilled style={{ color: "#faad14" }} /> : <StarOutlined />}
                        onClick={() => handleToggleWatchlist(pick)}
                      >
                        {isFavorited ? "已选" : "自选"}
                      </Button>
                    </div>
                  </div>
                );
              })}
            </div>
          </div>
        ) : null}

        {/* 策略风格分类筛选 */}
        {items.length > 0 ? (
          <div style={{ marginBottom: t.space[3] }}>
            <Segmented
              aria-label="策略意图分类"
              value={intentFilter}
              options={[
                { label: `全部候选 (${items.length})`, value: "ALL" },
                { label: `🏹 趋势先锋/顺势突破 (${counts.pioneer})`, value: "pioneer" },
                { label: `🛡️ 机构中军 (${counts.anchor})`, value: "anchor" },
                { label: `💎 超跌反转 (${counts.reversal})`, value: "reversal" },
                { label: `⭐ 价值优选 (${counts.quality})`, value: "quality" },
                { label: `⚠️ 风险预警 (${counts.risk})`, value: "risk" },
              ]}
              onChange={(val) => setIntentFilter(String(val))}
            />
          </div>
        ) : null}

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
            dataSource={filteredItems}
            rowKey={(record) => `${record.code}-${record.score}`}
            size="small"
            pagination={{ pageSize: 20, showSizeChanger: false }}
            scroll={{ x: "max-content" }}
            expandable={{
              expandedRowRender: (record) => (
                <div style={{ display: "grid", gap: t.space[2], padding: `${t.space[1]} 0` }}>
                  <Text className="u-text-secondary">{record.reason || "暂无入选说明"}</Text>
                  <div className="potential-tags-row">
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
                    <div className="potential-tags-row">
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
        <Text type="secondary" className="u-text-xs">
          说明：候选池按成交额/活跃度/估值质量三层筛选，并剔除 ST/次新/低流动性标的；评分 = 策略信号分（策略族封顶、信号时效衰减、市场环境加权）
          + 质量分（趋势/量能/估值/行业强弱/风险扣分）+ 基本面分（ROE/增长/负债/现金流）+ 题材分（当日热门题材/行业），输出按行业分散。仅供研究参考，不构成投资建议。股票名称可点击进入
          <Link to="/screener" className="u-text-primary">选股器</Link>
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
              <div style={{ display: "grid", gridTemplateColumns: "repeat(auto-fit, minmax(110px, 1fr))", gap: t.space[2] }}>
                <div className="potential-metric-tile">
                  <div className="u-text-secondary u-text-xs">胜率</div>
                  <div className="potential-text-primary u-text-bold u-font-mono">
                    {performanceQuery.data.win_rate != null ? `${(performanceQuery.data.win_rate * 100).toFixed(0)}%` : "-"}
                  </div>
                </div>
                <div className="potential-metric-tile">
                  <div className="u-text-secondary u-text-xs">盈亏比</div>
                  <div className="potential-text-primary u-text-bold u-font-mono">
                    {performanceQuery.data.profit_loss_ratio != null ? performanceQuery.data.profit_loss_ratio.toFixed(2) : "-"}
                  </div>
                </div>
                <div className="potential-metric-tile">
                  <div className="u-text-secondary u-text-xs">涨跌分布</div>
                  <div style={{ fontSize: t.font.xs, fontWeight: Number(t.weight.semibold), fontFamily: "var(--c-font-mono)", marginTop: 2 }}>
                    <span style={{ color: c.up }}>{performanceQuery.data.positive_count ?? 0}涨</span>
                    <span style={{ color: c.textMuted, margin: "0 2px" }}>/</span>
                    <span style={{ color: c.down }}>{performanceQuery.data.negative_count ?? 0}跌</span>
                  </div>
                </div>
                <div className="potential-metric-tile">
                  <div className="u-text-secondary u-text-xs">平均收益</div>
                  <div className="u-text-bold"><ChangeValue value={performanceQuery.data.average_return_pct} /></div>
                </div>
                <div className="potential-metric-tile">
                  <div className="u-text-secondary u-text-xs">中位收益</div>
                  <div className="u-text-bold"><ChangeValue value={performanceQuery.data.median_return_pct} /></div>
                </div>
                <div className="potential-metric-tile">
                  <div className="u-text-secondary u-text-xs">平均超额</div>
                  <div className="u-text-bold"><ChangeValue value={performanceQuery.data.average_excess_pct} /></div>
                </div>
                <div className="potential-metric-tile">
                  <div className="u-text-secondary u-text-xs">沪深300</div>
                  <div className="u-text-bold"><ChangeValue value={performanceQuery.data.benchmark_return_pct} /></div>
                </div>
              </div>
              <Text type="secondary" className="u-text-xs">
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
                <Text type="secondary" className="u-text-xs">{performanceQuery.data.message}</Text>
              ) : null}
            </div>
          ) : (
            <Text type="secondary">{performanceQuery.data.message ?? "暂无足够的前瞻数据"}</Text>
          )
        ) : (
          <Text type="secondary">暂无历史表现数据</Text>
        )}
      </Card>

      {previewStock ? (
        <StockWorkspaceDrawer
          open={Boolean(previewStock)}
          code={previewStock.code}
          name={previewStock.name}
          onClose={() => setPreviewStock(null)}
        />
      ) : null}
    </div>
  );
}
