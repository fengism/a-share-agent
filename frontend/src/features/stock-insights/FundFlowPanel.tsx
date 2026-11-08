import { useCallback, useMemo, useState } from "react";
import { Alert, Button, Card, Col, Row, Segmented, Table, Typography, Tag } from "antd";
import ReactEChartsCore from "echarts-for-react/lib/core";
import echarts from "../../charts/echarts-setup";
import { useStockFundFlowPages } from "../../api/queries";
import ResponsiveMetricGrid from "../../components/ResponsiveMetricGrid";
import SectionDataState from "../../components/SectionDataState";
import { useMediaQuery } from "../../hooks/useMediaQuery";
import { useColors } from "../../theme/hooks";
import { APP_FONT_SIZE } from "../../theme/typography";
import type { StockFundFlowItem } from "../../types/stock";
import { formatAmount } from "../../utils/format";
import "./fund-flow-panel.css";

const { Text } = Typography;

function formatNet(value: number | null): { text: string; modifier: "up" | "down" | "muted" } {
  if (value === null) return { text: "-", modifier: "muted" };
  if (value > 0) return { text: `+${formatAmount(value)}`, modifier: "up" };
  if (value < 0) return { text: formatAmount(value), modifier: "down" };
  return { text: formatAmount(value), modifier: "muted" };
}

function fundFlowDateIdentity(value: string) {
  const text = value.trim();
  const compact = text.match(/^(\d{4})(\d{2})(\d{2})$/);
  if (compact) return `${compact[1]}-${compact[2]}-${compact[3]}`;
  const separated = text.match(/^(\d{4})[-/](\d{2})[-/](\d{2})(?:\D.*)?$/);
  return separated ? `${separated[1]}-${separated[2]}-${separated[3]}` : text;
}

function FlowTile({ label, value }: { label: string; value: number | null }) {
  const fmt = formatNet(value);
  return (
    <div className="fund-flow-panel__tile">
      <div className="fund-flow-panel__tile-label">{label}</div>
      <div className={`fund-flow-panel__tile-value fund-flow-panel__tile-value--${fmt.modifier}`}>{fmt.text}</div>
    </div>
  );
}

export default function FundFlowPanel({ code, isExportingPdf = false }: { code: string; isExportingPdf?: boolean }) {
  const c = useColors();
  const isNarrow = useMediaQuery("(max-width: 768px)");
  const query = useStockFundFlowPages(code);
  const { isLoading, error, refetch } = query;
  const data = useMemo(() => query.data?.pages.flatMap((page) => page.items), [query.data]);
  const total = query.data?.pages[0]?.total ?? 0;

  const recentData = useMemo(() => {
    const uniqueByDate = new Map<string, StockFundFlowItem>();
    for (const item of data ?? []) {
      const dateIdentity = fundFlowDateIdentity(item.date);
      if (!uniqueByDate.has(dateIdentity)) uniqueByDate.set(dateIdentity, item);
    }
    return Array.from(uniqueByDate.entries())
      .sort(([leftDate], [rightDate]) => rightDate.localeCompare(leftDate))
      .map(([, item]) => item)
      .slice(0, 60);
  }, [data]);
  const latest = recentData[0] ?? null;
  const isStale = useMemo(() => recentData.some((item) => item.is_stale), [recentData]);
  const [chartDays, setChartDays] = useState<number>(60);
  const chartData = useMemo(() => recentData.slice(0, chartDays), [recentData, chartDays]);

  const cumulativeMainNet = useMemo(() => {
    return chartData.reduce((acc, item) => acc + (item.main_net ?? 0), 0);
  }, [chartData]);

  const chartOption = useMemo(() => {
    if (chartData.length === 0) return null;
    const recent = [...chartData].reverse();
    const dates = recent.map((d) => d.date.slice(5));
    const mainNets = recent.map((d) => d.main_net === null ? null : +(d.main_net / 1e8).toFixed(2));
    return {
      tooltip: { trigger: "axis" as const, axisPointer: { type: "shadow" as const } },
      grid: { left: 60, right: 20, top: 20, bottom: 30 },
      xAxis: { type: "category" as const, data: dates, axisLabel: { fontSize: APP_FONT_SIZE.xs, color: c.textSecondary } },
      yAxis: { type: "value" as const, axisLabel: { fontSize: APP_FONT_SIZE.xs, color: c.textSecondary, formatter: (v: number) => `${v}亿` } },
      series: [
        {
          type: "bar",
          data: mainNets.map((v) => ({
            value: v,
            itemStyle: { color: v === null || v >= 0 ? c.up : c.down, borderRadius: [3, 3, 0, 0] },
          })),
          barMaxWidth: 18,
        },
      ],
    };
  }, [chartData, c.textSecondary, c.up, c.down]);

  const chartContainerStyle = useMemo(() => ({ height: 220 }), []);

  const columns = useMemo(() => {
    if (isNarrow) {
      return [
        { title: "日期", dataIndex: "date", key: "date", width: 110, render: (value: string) => <Text className="fund-flow-panel__table-date">{value}</Text> },
        {
          title: "主力净流入",
          dataIndex: "main_net",
          key: "main_net",
          width: 140,
          align: "right" as const,
          render: (value: number | null) => value === null ? (
            <Tag>{formatNet(value).text}</Tag>
          ) : (
            <Tag className={`fund-flow-panel__table-tag fund-flow-panel__table-tag--${value >= 0 ? "up" : "down"}`}>{formatNet(value).text}</Tag>
          ),
        },
        {
          title: "超大单", dataIndex: "super_net", key: "super_net", width: 110, align: "right" as const,
          render: (value: number | null) => <span className={`fund-flow-panel__text--medium fund-flow-panel__text--${formatNet(value).modifier}`}>{formatNet(value).text}</span>,
        },
        {
          title: "大单", dataIndex: "large_net", key: "large_net", width: 100, align: "right" as const,
          render: (value: number | null) => <span className={`fund-flow-panel__text--${formatNet(value).modifier}`}>{formatNet(value).text}</span>,
        },
        {
          title: "中单", dataIndex: "mid_net", key: "mid_net", width: 100, align: "right" as const,
          render: (value: number | null) => <span className={`fund-flow-panel__text--${value === null ? "muted" : value >= 0 ? "down" : "up"}`}>{formatNet(value).text}</span>,
        },
        {
          title: "小单", dataIndex: "small_net", key: "small_net", width: 100, align: "right" as const,
          render: (value: number | null) => <span className={`fund-flow-panel__text--${value === null ? "muted" : value >= 0 ? "down" : "up"}`}>{formatNet(value).text}</span>,
        },
      ];
    }

    return [
      { title: "日期", dataIndex: "date", key: "date", width: 100, render: (value: string) => <Text className="fund-flow-panel__table-date">{value}</Text> },
      {
        title: "主力净流入", dataIndex: "main_net", key: "main_net", width: 130, align: "right" as const,
        render: (value: number | null) => value === null ? (
          <Tag>{formatNet(value).text}</Tag>
        ) : (
          <Tag className={`fund-flow-panel__table-tag fund-flow-panel__table-tag--${value >= 0 ? "up" : "down"}`}>{formatNet(value).text}</Tag>
        ),
      },
      {
        title: "超大单", dataIndex: "super_net", key: "super_net", width: 110, align: "right" as const,
        render: (value: number | null) => <span className={`fund-flow-panel__text--medium fund-flow-panel__text--${formatNet(value).modifier}`}>{formatNet(value).text}</span>,
      },
      {
        title: "大单", dataIndex: "large_net", key: "large_net", width: 100, align: "right" as const,
        render: (value: number | null) => <span className={`fund-flow-panel__text--${formatNet(value).modifier}`}>{formatNet(value).text}</span>,
      },
      {
        title: "中单", dataIndex: "mid_net", key: "mid_net", width: 100, align: "right" as const,
        render: (value: number | null) => <span className={`fund-flow-panel__text--${value === null ? "muted" : value >= 0 ? "down" : "up"}`}>{formatNet(value).text}</span>,
      },
      {
        title: "小单", dataIndex: "small_net", key: "small_net", width: 100, align: "right" as const,
        render: (value: number | null) => <span className={`fund-flow-panel__text--${value === null ? "muted" : value >= 0 ? "down" : "up"}`}>{formatNet(value).text}</span>,
      },
    ];
  }, [isNarrow]);

  const renderExpandedRow = useCallback((record: StockFundFlowItem) => (
    <ResponsiveMetricGrid
      items={[
        { key: "super", label: "超大单", value: formatNet(record.super_net).text },
        { key: "large", label: "大单", value: formatNet(record.large_net).text },
        { key: "mid", label: "中单", value: formatNet(record.mid_net).text },
        { key: "small", label: "小单", value: formatNet(record.small_net).text },
      ]}
    />
  ), []);

  return (
    <SectionDataState
      isLoading={isLoading}
      error={data?.length ? null : error}
      onRetry={() => refetch()}
      isEmpty={!data || data.length === 0}
      emptyText="暂无资金流向数据"
      errorTitle="资金流向加载失败"
      skeletonRows={5}
      minHeight={260}
    >
      <div className="fund-flow-panel__container">
      {isStale ? (
        <Alert
          type="warning"
          showIcon
          title="资金流上游暂不可用，当前展示最近一次成功缓存"
        />
      ) : null}
      {recentData.some((item) => item.source === "tdxhub_stock_fund_flow_estimate") ? (
        <Alert
          type="info"
          showIcon
          title="备选数据源：TDXHub 分笔估算"
          description="按分笔成交金额分档计算，非交易所官方资金流，与百度、东方财富口径可能不同；主力、大单等仅为金额分档，不代表交易者身份。"
        />
      ) : null}
      <div className="fund-flow-panel__meta-row">
        <Text type="secondary">已加载 {recentData.length} / {total} 个交易日 · 每批最多 20 日</Text>
        {query.hasNextPage && !isExportingPdf ? (
          <Button aria-label={query.isFetchNextPageError ? "重试加载更多" : "加载更多"} loading={query.isFetchingNextPage} onClick={() => { void query.fetchNextPage(); }}>
            {query.isFetchNextPageError ? "重试加载更多" : "加载更多"}
          </Button>
        ) : null}
      </div>
      {error && data?.length ? (
        <Alert
          type="warning"
          showIcon
          title="后续批次加载失败，已加载数据仍可查看"
          description={error instanceof Error ? error.message : "请稍后重试"}
          action={<Button onClick={() => { void refetch(); }}>重新加载</Button>}
        />
      ) : null}
      {/* Summary cards for latest day */}
      {latest && (
        <div className="fund-flow-panel__summary-grid">
          <Row gutter={[10, 10]}>
            <Col xs={12} sm={8}><FlowTile label="主力净流入" value={latest.main_net} /></Col>
            <Col xs={12} sm={8}><FlowTile label="超大单净流入" value={latest.super_net} /></Col>
            <Col xs={12} sm={8}><FlowTile label="大单净流入" value={latest.large_net} /></Col>
            <Col xs={12} sm={8}><FlowTile label="中单净流入" value={latest.mid_net} /></Col>
            <Col xs={12} sm={8}><FlowTile label="小单净流入" value={latest.small_net} /></Col>
            <Col xs={12} sm={8}>
              <div className="fund-flow-panel__tile">
                <div className="fund-flow-panel__tile-label">统计日期</div>
                <div className="fund-flow-panel__tile-value fund-flow-panel__tile-value--primary">{latest.date}</div>
              </div>
            </Col>
          </Row>

          {/* 主力 vs 散户 筹码博弈诊断 */}
          {(() => {
            const mainVal = latest.main_net ?? ((latest.super_net ?? 0) + (latest.large_net ?? 0));
            const retailVal = (latest.mid_net ?? 0) + (latest.small_net ?? 0);
            let stanceLabel = "资金存量博弈，多空震荡整理";
            let stanceTagColor: "primary" | "up" | "down" | "warning" = "primary";

            if (mainVal > 0 && retailVal < 0) {
              stanceLabel = "主力吸筹进场，散户加速筹码离场（筹码集中）";
              stanceTagColor = "up";
            } else if (mainVal > 0 && retailVal >= 0) {
              stanceLabel = "主力与各方资金合力净流入，做多动能充沛";
              stanceTagColor = "up";
            } else if (mainVal < 0 && retailVal > 0) {
              stanceLabel = "主力大资金减仓派发，散户买单接盘（警惕承压）";
              stanceTagColor = "down";
            } else if (mainVal < 0 && retailVal <= 0) {
              stanceLabel = "场内资金全线净流出，防守避险情绪浓厚";
              stanceTagColor = "warning";
            }

            return (
              <div className="fund-flow-panel__diagnosis-card">
                <div className="fund-flow-panel__diagnosis-left">
                  <Text strong className="fund-flow-panel__diagnosis-title">博弈诊断：</Text>
                  <Tag className={`fund-flow-panel__diagnosis-tag fund-flow-panel__diagnosis-tag--${stanceTagColor}`}>{stanceLabel}</Tag>
                </div>
                <div className="fund-flow-panel__diagnosis-stats">
                  <span>主力合计: <strong className={mainVal >= 0 ? "fund-flow-panel__text--up" : "fund-flow-panel__text--down"}>{mainVal > 0 ? `+${formatAmount(mainVal)}` : formatAmount(mainVal)}</strong></span>
                  <span>散户合计: <strong className={retailVal >= 0 ? "fund-flow-panel__text--up" : "fund-flow-panel__text--down"}>{retailVal > 0 ? `+${formatAmount(retailVal)}` : formatAmount(retailVal)}</strong></span>
                </div>
              </div>
            );
          })()}
        </div>
      )}

      {/* Bar chart */}
      {chartOption && (
        <Card size="small" className="u-card" styles={{ body: { padding: 8 } }}>
          <div className="fund-flow-panel__chart-header">
            <div className="fund-flow-panel__chart-title-wrap">
              <Text className="fund-flow-panel__chart-title">
                主力净流入走势（近 {chartData.length} 日）
              </Text>
              {chartData.length > 0 && (
                <span className="fund-flow-panel__chart-cumulative">
                  累计: <strong className={`fund-flow-panel__chart-cumulative-val ${cumulativeMainNet >= 0 ? "fund-flow-panel__chart-cumulative-val--up" : "fund-flow-panel__chart-cumulative-val--down"}`}>
                    {cumulativeMainNet > 0 ? `+${formatAmount(cumulativeMainNet)}` : formatAmount(cumulativeMainNet)}
                  </strong>
                </span>
              )}
            </div>
            {!isExportingPdf && (
              <Segmented
                size="small"
                aria-label="资金流向周期"
                options={[
                  { label: "近5日", value: 5 },
                  { label: "近20日", value: 20 },
                  { label: "近60日", value: 60 },
                ]}
                value={chartDays}
                onChange={(val) => setChartDays(Number(val))}
              />
            )}
          </div>
          <ReactEChartsCore echarts={echarts} option={chartOption} style={chartContainerStyle} notMerge />
        </Card>
      )}

      {/* Data table */}
      <Card size="small" className="u-card" styles={{ body: { padding: 0 } }}>
        <Table
          dataSource={recentData}
          columns={columns}
          rowKey="date"
          pagination={isExportingPdf ? false : { pageSize: 15, showSizeChanger: false, simple: true }}
          size="small"
          expandable={isNarrow ? {
            expandedRowRender: renderExpandedRow,
            columnWidth: 38,
          } : undefined}
          scroll={isNarrow ? undefined : { x: 600 }}
        />
      </Card>
      </div>
    </SectionDataState>
  );
}
