import { useMemo } from "react";
import { Card, Col, Row, Table, Spin, Typography, Tag } from "antd";
import ReactEChartsCore from "echarts-for-react/lib/core";
import echarts from "../../charts/echarts-setup";
import { useStockFundFlow } from "../../api/queries";
import { useColors, useStyles } from "../../theme/hooks";
import { formatAmount } from "../../utils/format";

const { Text } = Typography;

interface NetColors { up: string; down: string; muted: string }

function formatNet(value: number, colors: NetColors): { text: string; color: string } {
  if (value > 0) return { text: `+${formatAmount(value)}`, color: colors.up };
  if (value < 0) return { text: formatAmount(value), color: colors.down };
  return { text: formatAmount(value), color: colors.muted };
}

function FlowTile({ label, value, colors }: { label: string; value: number; colors: { textSecondary: string; elevatedBg: string; border: string } & NetColors }) {
  const fmt = formatNet(value, colors);
  return (
    <div style={{ padding: "14px 12px", background: colors.elevatedBg, border: `1px solid ${colors.border}`, borderRadius: 10, textAlign: "center" }}>
      <div style={{ color: colors.textSecondary, fontSize: 12, marginBottom: 4 }}>{label}</div>
      <div style={{ fontSize: 14, fontWeight: 700, color: fmt.color, lineHeight: 1.3 }}>{fmt.text}</div>
    </div>
  );
}

export default function FundFlowPanel({ code }: { code: string }) {
  const c = useColors();
  const { cardStyle } = useStyles();
  const { data, isLoading } = useStockFundFlow(code);
  const net: NetColors = { up: c.up, down: c.down, muted: c.textMuted };

  const latest = useMemo(() => data?.[0] ?? null, [data]);
  const chartOption = useMemo(() => {
    if (!data || data.length === 0) return null;
    const recent = data.slice(0, 60).reverse();
    const dates = recent.map((d) => d.date.slice(5));
    const mainNets = recent.map((d) => +(d.main_net / 1e8).toFixed(2));
    return {
      tooltip: { trigger: "axis" as const, axisPointer: { type: "shadow" as const } },
      grid: { left: 60, right: 20, top: 20, bottom: 30 },
      xAxis: { type: "category" as const, data: dates, axisLabel: { fontSize: 10, color: c.textSecondary } },
      yAxis: { type: "value" as const, axisLabel: { fontSize: 10, color: c.textSecondary, formatter: (v: number) => `${v}亿` } },
      series: [
        {
          type: "bar",
          data: mainNets.map((v) => ({
            value: v,
            itemStyle: { color: v >= 0 ? c.up : c.down, borderRadius: [3, 3, 0, 0] },
          })),
          barMaxWidth: 18,
        },
      ],
    };
  }, [data, c.textSecondary, c.up, c.down]);

  if (isLoading) return <Spin style={{ display: "block", margin: "40px auto" }} />;
  if (!data || data.length === 0) return <Text type="secondary">暂无资金流向数据</Text>;

  const tileColors = { textSecondary: c.textSecondary, elevatedBg: c.elevatedBg, border: c.border, up: c.up, down: c.down, muted: c.textMuted };

  const columns = [
    { title: "日期", dataIndex: "date", key: "date", width: 100, render: (v: string) => <Text style={{ fontWeight: 500 }}>{v}</Text> },
    {
      title: "主力净流入", dataIndex: "main_net", key: "main_net", width: 130, align: "right" as const,
      render: (v: number) => <Tag color={v >= 0 ? "red" : "green"} style={{ fontWeight: 600 }}>{formatNet(v, net).text}</Tag>,
    },
    {
      title: "超大单", dataIndex: "super_net", key: "super_net", width: 110, align: "right" as const,
      render: (v: number) => <span style={{ color: v >= 0 ? c.up : c.down, fontWeight: 500 }}>{formatNet(v, net).text}</span>,
    },
    {
      title: "大单", dataIndex: "large_net", key: "large_net", width: 100, align: "right" as const,
      render: (v: number) => <span style={{ color: v >= 0 ? c.up : c.down }}>{formatNet(v, net).text}</span>,
    },
    {
      title: "中单", dataIndex: "mid_net", key: "mid_net", width: 100, align: "right" as const,
      render: (v: number) => <span style={{ color: v >= 0 ? c.down : c.up }}>{formatNet(v, net).text}</span>,
    },
    {
      title: "小单", dataIndex: "small_net", key: "small_net", width: 100, align: "right" as const,
      render: (v: number) => <span style={{ color: v >= 0 ? c.down : c.up }}>{formatNet(v, net).text}</span>,
    },
  ];

  return (
    <div style={{ display: "grid", gap: 16 }}>
      {/* Summary cards for latest day */}
      {latest && (
        <Row gutter={[10, 10]}>
          <Col xs={12} sm={8}><FlowTile label="主力净流入" value={latest.main_net} colors={tileColors} /></Col>
          <Col xs={12} sm={8}><FlowTile label="超大单净流入" value={latest.super_net} colors={tileColors} /></Col>
          <Col xs={12} sm={8}><FlowTile label="大单净流入" value={latest.large_net} colors={tileColors} /></Col>
          <Col xs={12} sm={8}><FlowTile label="中单净流入" value={latest.mid_net} colors={tileColors} /></Col>
          <Col xs={12} sm={8}><FlowTile label="小单净流入" value={latest.small_net} colors={tileColors} /></Col>
          <Col xs={12} sm={8}>
            <div style={{ padding: "14px 12px", background: c.elevatedBg, border: `1px solid ${c.border}`, borderRadius: 10, textAlign: "center" }}>
              <div style={{ color: c.textSecondary, fontSize: 12, marginBottom: 4 }}>统计日期</div>
              <div style={{ fontSize: 14, fontWeight: 700, color: c.textPrimary }}>{latest.date}</div>
            </div>
          </Col>
        </Row>
      )}

      {/* Bar chart */}
      {chartOption && (
        <Card size="small" style={cardStyle} styles={{ body: { padding: 8 } }}>
          <Text style={{ fontSize: 13, fontWeight: 600, color: c.textPrimary, marginBottom: 4, display: "block", paddingLeft: 4 }}>主力净流入走势（近60日）</Text>
          <ReactEChartsCore echarts={echarts} option={chartOption} style={{ height: 220 }} notMerge />
        </Card>
      )}

      {/* Data table */}
      <Card size="small" style={cardStyle} styles={{ body: { padding: 0 } }}>
        <Table
          dataSource={data}
          columns={columns}
          rowKey="date"
          pagination={{ pageSize: 15, showSizeChanger: false, simple: true }}
          size="small"
          scroll={{ x: 600 }}
        />
      </Card>
    </div>
  );
}
