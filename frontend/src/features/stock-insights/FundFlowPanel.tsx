import { useCallback, useMemo } from "react";
import { Alert, Card, Col, Row, Table, Typography, Tag } from "antd";
import ReactEChartsCore from "echarts-for-react/lib/core";
import echarts from "../../charts/echarts-setup";
import { useStockFundFlow } from "../../api/queries";
import ResponsiveMetricGrid from "../../components/ResponsiveMetricGrid";
import SectionDataState from "../../components/SectionDataState";
import { useMediaQuery } from "../../hooks/useMediaQuery";
import { useColors, useStyles, semanticTagStyle } from "../../theme/hooks";
import { APP_FONT_SIZE } from "../../theme/typography";
import type { StockFundFlowItem } from "../../types/stock";
import { formatAmount } from "../../utils/format";

const { Text } = Typography;

interface NetColors { up: string; down: string; muted: string }

function formatNet(value: number | null, colors: NetColors): { text: string; color: string } {
  if (value === null) return { text: "-", color: colors.muted };
  if (value > 0) return { text: `+${formatAmount(value)}`, color: colors.up };
  if (value < 0) return { text: formatAmount(value), color: colors.down };
  return { text: formatAmount(value), color: colors.muted };
}

function fundFlowDateIdentity(value: string) {
  const text = value.trim();
  const compact = text.match(/^(\d{4})(\d{2})(\d{2})$/);
  if (compact) return `${compact[1]}-${compact[2]}-${compact[3]}`;
  const separated = text.match(/^(\d{4})[-/](\d{2})[-/](\d{2})(?:\D.*)?$/);
  return separated ? `${separated[1]}-${separated[2]}-${separated[3]}` : text;
}

function FlowTile({ label, value, colors }: { label: string; value: number | null; colors: { textSecondary: string; hoverBg: string; border: string } & NetColors }) {
  const fmt = formatNet(value, colors);
  return (
    <div style={{ padding: "14px 12px", background: colors.hoverBg, border: `1px solid ${colors.border}`, borderRadius: 10, textAlign: "center" }}>
      <div style={{ color: colors.textSecondary, fontSize: "var(--c-font-sm)", marginBottom: 4 }}>{label}</div>
      <div style={{ fontSize: "var(--c-font-base)", fontWeight: "var(--c-weight-bold)", color: fmt.color, lineHeight: "var(--c-leading-tight)" }}>{fmt.text}</div>
    </div>
  );
}

export default function FundFlowPanel({ code, isExportingPdf = false }: { code: string; isExportingPdf?: boolean }) {
  const c = useColors();
  const isNarrow = useMediaQuery("(max-width: 768px)");
  const { cardStyle } = useStyles();
  const { data, isLoading, error, refetch } = useStockFundFlow(code);
  const net = useMemo<NetColors>(
    () => ({ up: c.up, down: c.down, muted: c.textMuted }),
    [c.down, c.textMuted, c.up],
  );

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
  const chartOption = useMemo(() => {
    if (recentData.length === 0) return null;
    const recent = [...recentData].reverse();
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
  }, [recentData, c.textSecondary, c.up, c.down]);

  const tileColors = { textSecondary: c.textSecondary, hoverBg: c.hoverBg, border: c.border, up: c.up, down: c.down, muted: c.textMuted };

  const columns = useMemo(() => {
    if (isNarrow) {
      return [
        { title: "日期", dataIndex: "date", key: "date", width: 110, render: (value: string) => <Text style={{ fontWeight: "var(--c-weight-medium)" }}>{value}</Text> },
        {
          title: "主力净流入",
          dataIndex: "main_net",
          key: "main_net",
          width: 140,
          align: "right" as const,
          render: (value: number | null) => value === null ? (
            <Tag>{formatNet(value, net).text}</Tag>
          ) : (
            <Tag style={{ ...semanticTagStyle(value >= 0 ? "up" : "down"), fontWeight: "var(--c-weight-semibold)" }}>{formatNet(value, net).text}</Tag>
          ),
        },
        {
          title: "超大单", dataIndex: "super_net", key: "super_net", width: 110, align: "right" as const,
          render: (value: number | null) => <span style={{ color: formatNet(value, net).color, fontWeight: "var(--c-weight-medium)" }}>{formatNet(value, net).text}</span>,
        },
        {
          title: "大单", dataIndex: "large_net", key: "large_net", width: 100, align: "right" as const,
          render: (value: number | null) => <span style={{ color: formatNet(value, net).color }}>{formatNet(value, net).text}</span>,
        },
        {
          title: "中单", dataIndex: "mid_net", key: "mid_net", width: 100, align: "right" as const,
          render: (value: number | null) => <span style={{ color: value === null ? net.muted : value >= 0 ? c.down : c.up }}>{formatNet(value, net).text}</span>,
        },
        {
          title: "小单", dataIndex: "small_net", key: "small_net", width: 100, align: "right" as const,
          render: (value: number | null) => <span style={{ color: value === null ? net.muted : value >= 0 ? c.down : c.up }}>{formatNet(value, net).text}</span>,
        },
      ];
    }

    return [
      { title: "日期", dataIndex: "date", key: "date", width: 100, render: (value: string) => <Text style={{ fontWeight: "var(--c-weight-medium)" }}>{value}</Text> },
      {
        title: "主力净流入", dataIndex: "main_net", key: "main_net", width: 130, align: "right" as const,
        render: (value: number | null) => value === null ? (
          <Tag>{formatNet(value, net).text}</Tag>
        ) : (
          <Tag style={{ ...semanticTagStyle(value >= 0 ? "up" : "down"), fontWeight: "var(--c-weight-semibold)" }}>{formatNet(value, net).text}</Tag>
        ),
      },
      {
        title: "超大单", dataIndex: "super_net", key: "super_net", width: 110, align: "right" as const,
        render: (value: number | null) => <span style={{ color: formatNet(value, net).color, fontWeight: "var(--c-weight-medium)" }}>{formatNet(value, net).text}</span>,
      },
      {
        title: "大单", dataIndex: "large_net", key: "large_net", width: 100, align: "right" as const,
        render: (value: number | null) => <span style={{ color: formatNet(value, net).color }}>{formatNet(value, net).text}</span>,
      },
      {
        title: "中单", dataIndex: "mid_net", key: "mid_net", width: 100, align: "right" as const,
        render: (value: number | null) => <span style={{ color: value === null ? net.muted : value >= 0 ? c.down : c.up }}>{formatNet(value, net).text}</span>,
      },
      {
        title: "小单", dataIndex: "small_net", key: "small_net", width: 100, align: "right" as const,
        render: (value: number | null) => <span style={{ color: value === null ? net.muted : value >= 0 ? c.down : c.up }}>{formatNet(value, net).text}</span>,
      },
    ];
  }, [c.down, c.up, isNarrow, net]);

  const renderExpandedRow = useCallback((record: StockFundFlowItem) => (
    <ResponsiveMetricGrid
      items={[
        { key: "super", label: "超大单", value: formatNet(record.super_net, net).text },
        { key: "large", label: "大单", value: formatNet(record.large_net, net).text },
        { key: "mid", label: "中单", value: formatNet(record.mid_net, net).text },
        { key: "small", label: "小单", value: formatNet(record.small_net, net).text },
      ]}
    />
  ), [net]);

  return (
    <SectionDataState
      isLoading={isLoading}
      error={error}
      onRetry={() => refetch()}
      isEmpty={!data || data.length === 0}
      emptyText="暂无资金流向数据"
      errorTitle="资金流向加载失败"
      skeletonRows={5}
      minHeight={260}
    >
      <div style={{ display: "grid", gap: 16 }}>
      {isStale ? (
        <Alert
          type="warning"
          showIcon
          title="资金流上游暂不可用，当前展示最近一次成功缓存"
        />
      ) : null}
      {/* Summary cards for latest day */}
      {latest && (
        <Row gutter={[10, 10]}>
          <Col xs={12} sm={8}><FlowTile label="主力净流入" value={latest.main_net} colors={tileColors} /></Col>
          <Col xs={12} sm={8}><FlowTile label="超大单净流入" value={latest.super_net} colors={tileColors} /></Col>
          <Col xs={12} sm={8}><FlowTile label="大单净流入" value={latest.large_net} colors={tileColors} /></Col>
          <Col xs={12} sm={8}><FlowTile label="中单净流入" value={latest.mid_net} colors={tileColors} /></Col>
          <Col xs={12} sm={8}><FlowTile label="小单净流入" value={latest.small_net} colors={tileColors} /></Col>
          <Col xs={12} sm={8}>
            <div style={{ padding: "14px 12px", background: c.hoverBg, border: `1px solid ${c.border}`, borderRadius: 10, textAlign: "center" }}>
              <div style={{ color: c.textSecondary, fontSize: "var(--c-font-sm)", marginBottom: 4 }}>统计日期</div>
              <div style={{ fontSize: "var(--c-font-base)", fontWeight: "var(--c-weight-bold)", color: c.textPrimary }}>{latest.date}</div>
            </div>
          </Col>
        </Row>
      )}

      {/* Bar chart */}
      {chartOption && (
        <Card size="small" style={cardStyle} styles={{ body: { padding: 8 } }}>
          <Text style={{ fontSize: "var(--c-font-md)", fontWeight: "var(--c-weight-semibold)", color: c.textPrimary, marginBottom: 4, display: "block", paddingLeft: 4 }}>主力净流入走势（近60日）</Text>
          <ReactEChartsCore echarts={echarts} option={chartOption} style={{ height: 220 }} notMerge />
        </Card>
      )}

      {/* Data table */}
      <Card size="small" style={cardStyle} styles={{ body: { padding: 0 } }}>
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
