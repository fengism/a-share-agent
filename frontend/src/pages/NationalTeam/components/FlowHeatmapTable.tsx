import { useCallback, useMemo, useState } from "react";
import { Button, Card, Col, message, Modal, Row, Segmented, Space, Statistic, Table, Tag, Tooltip, Typography } from "antd";
import type { ColumnsType } from "antd/es/table";
import { DownloadOutlined, FallOutlined, InfoCircleOutlined, RiseOutlined, TableOutlined } from "@ant-design/icons";
import { useColors } from "../../../styles/ui";
import { formatNumberWithSeparators } from "../../../utils/format";
import type { NationalTeamDailyFlow } from "../../../types/stock";
import { useMediaQuery } from "../../../hooks/useMediaQuery";
import { downloadCsv } from "../utils/csv";

const { Text } = Typography;

function formatSignedFlow(val: number | null | undefined, unit = "") {
  if (val == null || !Number.isFinite(val)) return "-";
  return `${val > 0 ? "+" : ""}${formatNumberWithSeparators(val, 2)}${unit ? " " + unit : ""}`;
}

const HEATMAP_INDICES = [
  "沪深300",
  "上证50",
  "中证A500",
  "中证500",
  "中证1000",
  "中证2000",
  "科创50",
  "科创100",
  "创业板",
  "红利低波",
] as const;

interface FlowHeatmapTableProps {
  dailyFlows?: NationalTeamDailyFlow[];
  asOfDate?: string | null;
}

export default function FlowHeatmapTable({ dailyFlows, asOfDate }: FlowHeatmapTableProps) {
  const colors = useColors();
  const isMobile = useMediaQuery("(max-width: 640px)");
  const [range, setRange] = useState<"20" | "30" | "all">("20");
  const [selectedDateFlow, setSelectedDateFlow] = useState<NationalTeamDailyFlow | null>(null);

  const sortedFlows = useMemo(() => {
    if (!dailyFlows || dailyFlows.length === 0) return [];
    // 倒序展示：最新日期在上
    const copy = [...dailyFlows].reverse();
    if (range === "20") return copy.slice(0, 20);
    if (range === "30") return copy.slice(0, 30);
    return copy;
  }, [dailyFlows, range]);

  // 计算所选时间窗内所有宽基单项的最大绝对值，用于归一化色阶
  const maxAbsFlow = useMemo(() => {
    let maxVal = 0.1;
    for (const row of sortedFlows) {
      if (row.flows_by_index) {
        for (const idx of HEATMAP_INDICES) {
          const val = Math.abs(row.flows_by_index[idx] ?? 0);
          if (val > maxVal) maxVal = val;
        }
      }
    }
    return maxVal;
  }, [sortedFlows]);

  // 导出矩阵为 CSV
  const handleExportCsv = () => {
    if (!sortedFlows.length) {
      message.warning("暂无矩阵数据可导出");
      return;
    }
    const headers = ["交易日期", "宽基合计(亿元)", ...HEATMAP_INDICES.map((name) => `${name}(亿元)`)];
    const rows = sortedFlows.map((row) => [
      row.date,
      row.total_flow_100m != null ? row.total_flow_100m.toFixed(2) : "",
      ...HEATMAP_INDICES.map((idx) => {
        const val = row.flows_by_index?.[idx];
        return val != null ? val.toFixed(2) : "";
      }),
    ]);
    const filename = `宽基ETF日度净流入矩阵_${asOfDate || "latest"}.csv`;
    downloadCsv(filename, [headers, ...rows]);
    message.success(`已导出 ${sortedFlows.length} 个交易日的宽基资金矩阵`);
  };

  // 根据资金流正负与相对强度计算热力单元格底色与字色
  const getCellStyle = useCallback((val: number | null | undefined): React.CSSProperties => {
    if (val == null || val === 0) {
      return { textAlign: "right", fontFamily: "var(--c-font-mono)", color: colors.textSecondary };
    }
    const ratio = Math.min(1, Math.max(0.12, Math.abs(val) / maxAbsFlow));
    const isPos = val > 0;
    // 使用红涨绿跌的平滑渐变透明度
    const bg = isPos
      ? `rgba(245, 34, 45, ${0.08 + ratio * 0.42})`
      : `rgba(82, 196, 26, ${0.08 + ratio * 0.42})`;
    const color = isPos ? colors.up : colors.down;

    return {
      background: bg,
      color,
      fontWeight: ratio > 0.5 ? 600 : 500,
      textAlign: "right",
      fontFamily: "var(--c-font-mono)",
      padding: "6px 8px",
      borderRadius: 4,
      transition: "background 0.2s ease",
      cursor: "pointer",
    };
  }, [colors.down, colors.textSecondary, colors.up, maxAbsFlow]);

  const columns: ColumnsType<NationalTeamDailyFlow> = useMemo(() => {
    const cols: ColumnsType<NationalTeamDailyFlow> = [
      {
        title: "交易日期",
        dataIndex: "date",
        key: "date",
        width: 105,
        fixed: "left",
        sorter: (a, b) => a.date.localeCompare(b.date),
        render: (date: string, row) => (
          <Button
            type="link"
            size="small"
            style={{ padding: 0, height: "auto", fontFamily: "var(--c-font-mono)", fontSize: 12, fontWeight: 600 }}
            onClick={() => setSelectedDateFlow(row)}
            title="点击下钻查看当日资金与板块细分"
          >
            {date}
          </Button>
        ),
      },
      {
        title: (
          <Tooltip title="当日所纳入全部核心宽基 ETF 的估算净申购总额；点击可下钻分析">
            <span style={{ cursor: "help" }}>
              宽基合计 <InfoCircleOutlined style={{ fontSize: 10, color: colors.textSecondary }} />
            </span>
          </Tooltip>
        ),
        dataIndex: "total_flow_100m",
        key: "total_flow_100m",
        width: 110,
        fixed: isMobile ? undefined : "left",
        sorter: (a, b) => (a.total_flow_100m ?? 0) - (b.total_flow_100m ?? 0),
        render: (val: number | null, row) => {
          if (val == null) return <span style={{ color: colors.textSecondary }}>-</span>;
          const isPos = val > 0;
          return (
            <Tooltip title={`${row.date} 全市场宽基估算净申购合计：${formatSignedFlow(val, "亿元")} (点击下钻)`}>
              <div
                onClick={() => setSelectedDateFlow(row)}
                style={{
                  textAlign: "right",
                  fontWeight: 700,
                  color: isPos ? colors.up : val < 0 ? colors.down : colors.textPrimary,
                  fontFamily: "var(--c-font-mono)",
                  cursor: "pointer",
                }}
              >
                {formatSignedFlow(val)}
              </div>
            </Tooltip>
          );
        },
      },
    ];

    for (const idxName of HEATMAP_INDICES) {
      cols.push({
        title: idxName,
        key: idxName,
        width: 96,
        sorter: (a, b) => (a.flows_by_index?.[idxName] ?? 0) - (b.flows_by_index?.[idxName] ?? 0),
        render: (_, row) => {
          const val = row.flows_by_index?.[idxName];
          return (
            <Tooltip title={`${row.date} · ${idxName} 估算净申购：${val != null ? formatSignedFlow(val, "亿元") : "暂无数据"}`}>
              <div style={getCellStyle(val)}>
                {val != null && val !== 0 ? formatSignedFlow(val) : "-"}
              </div>
            </Tooltip>
          );
        },
      });
    }

    return cols;
  }, [colors, getCellStyle, isMobile]);

  return (
    <Card
      className="national-team-heatmap-card"
      size="small"
      data-testid="national-team-flow-heatmap-table"
      title={
        <div style={{ display: "flex", alignItems: "center", justifyContent: "space-between", flexWrap: "wrap", gap: 8 }}>
          <Space size={8}>
            <TableOutlined style={{ color: colors.primary }} />
            <span style={{ fontWeight: 600, fontSize: 14 }}>宽基日度资金流向热力矩阵</span>
            <Tag color="cyan" style={{ fontSize: 11 }}>金额单位：亿元</Tag>
          </Space>
          <div style={{ display: "flex", alignItems: "center", gap: 10, flexWrap: "wrap" }}>
            {/* 颜色图例说明 */}
            <div style={{ display: "flex", alignItems: "center", gap: 6, fontSize: 11, color: colors.textSecondary }}>
              <span>流出</span>
              <span style={{ width: 14, height: 10, borderRadius: 2, background: "rgba(82, 196, 26, 0.45)" }} />
              <span style={{ width: 14, height: 10, borderRadius: 2, background: "rgba(245, 34, 45, 0.45)" }} />
              <span>流入</span>
            </div>
            <Segmented
              size="small"
              value={range}
              options={[
                { label: "近 20 日", value: "20" },
                { label: "近 30 日", value: "30" },
                { label: "全部", value: "all" },
              ]}
              onChange={(val) => setRange(val as "20" | "30" | "all")}
              className="national-team-segmented"
            />
            <Button
              size="small"
              icon={<DownloadOutlined />}
              onClick={handleExportCsv}
              disabled={!sortedFlows.length}
            >
              导出矩阵 CSV
            </Button>
          </div>
        </div>
      }
      styles={{ body: { padding: 0 } }}
    >
      <Table<NationalTeamDailyFlow>
        rowKey="date"
        columns={columns}
        dataSource={sortedFlows}
        pagination={false}
        scroll={{ x: 1200, y: 480 }}
        size="small"
        className="national-team-heatmap-grid"
      />
      <div style={{ padding: "8px 14px", borderTop: `1px solid ${colors.border}`, display: "flex", justifyContent: "space-between", fontSize: 11, color: colors.textSecondary }}>
        <span>口径说明：申赎金额估算值 = 当日份额变动 × 收盘价，非交易所逐笔真实结算现金；支持点击表头排序与点击日期下钻明细。</span>
        {asOfDate && <span>截至 {asOfDate}</span>}
      </div>

      {selectedDateFlow && (
        <Modal
          title={
            <Space size={8} align="center">
              <span style={{ fontSize: 16 }}>📅</span>
              <span>{selectedDateFlow.date} 宽基资金流向下钻分析</span>
              {selectedDateFlow.benchmark_close != null && (
                <Tag color="blue" style={{ fontSize: 11, margin: 0 }}>
                  基准收盘：{selectedDateFlow.benchmark_close.toFixed(1)} 点
                </Tag>
              )}
            </Space>
          }
          open={!!selectedDateFlow}
          onCancel={() => setSelectedDateFlow(null)}
          footer={[
            <Button
              key="close"
              type="primary"
              data-testid="drilldown-modal-close"
              onClick={() => setSelectedDateFlow(null)}
            >
              关闭
            </Button>,
          ]}
          width={680}
        >
          <div style={{ padding: "8px 0" }}>
            {/* 核心数据汇总 */}
            <Row gutter={[12, 12]} style={{ marginBottom: 16 }}>
              <Col span={8}>
                <Card size="small" style={{ background: "var(--c-bg-layout)", borderRadius: 6 }}>
                  <Statistic
                    title="当日宽基估算净申购"
                    value={selectedDateFlow.total_flow_100m != null ? `${selectedDateFlow.total_flow_100m > 0 ? "+" : ""}${selectedDateFlow.total_flow_100m.toFixed(2)} 亿元` : "-"}
                    valueStyle={{
                      color: (selectedDateFlow.total_flow_100m ?? 0) > 0 ? colors.up : (selectedDateFlow.total_flow_100m ?? 0) < 0 ? colors.down : colors.textPrimary,
                      fontFamily: "var(--c-font-mono)",
                      fontSize: 16,
                      fontWeight: 700,
                    }}
                    prefix={(selectedDateFlow.total_flow_100m ?? 0) > 0 ? <RiseOutlined /> : (selectedDateFlow.total_flow_100m ?? 0) < 0 ? <FallOutlined /> : undefined}
                  />
                </Card>
              </Col>
              <Col span={8}>
                <Card size="small" style={{ background: "var(--c-bg-layout)", borderRadius: 6 }}>
                  <Statistic
                    title="样本 ETF 成交额"
                    value={selectedDateFlow.total_amount_100m != null ? `${selectedDateFlow.total_amount_100m.toFixed(1)} 亿元` : "-"}
                    valueStyle={{ fontFamily: "var(--c-font-mono)", fontSize: 16, fontWeight: 700, color: colors.primary }}
                  />
                </Card>
              </Col>
              <Col span={8}>
                <Card size="small" style={{ background: "var(--c-bg-layout)", borderRadius: 6 }}>
                  <Statistic
                    title="区间累计净申购"
                    value={selectedDateFlow.cumulative_flow_100m != null ? `${selectedDateFlow.cumulative_flow_100m > 0 ? "+" : ""}${selectedDateFlow.cumulative_flow_100m.toFixed(1)} 亿元` : "-"}
                    valueStyle={{
                      color: (selectedDateFlow.cumulative_flow_100m ?? 0) > 0 ? colors.up : (selectedDateFlow.cumulative_flow_100m ?? 0) < 0 ? colors.down : colors.textPrimary,
                      fontFamily: "var(--c-font-mono)",
                      fontSize: 16,
                      fontWeight: 700,
                    }}
                  />
                </Card>
              </Col>
            </Row>

            {/* 板块资金拆解 */}
            {selectedDateFlow.flows_by_category && Object.keys(selectedDateFlow.flows_by_category).length > 0 && (
              <div style={{ marginBottom: 16 }}>
                <Text strong style={{ fontSize: 13, marginBottom: 8, display: "block" }}>战术板块资金拆解</Text>
                <Row gutter={[8, 8]}>
                  {[
                    { key: "core_broad", label: "核心大盘", color: "blue" },
                    { key: "a500", label: "新质A500", color: "gold" },
                    { key: "growth", label: "中小成长", color: "cyan" },
                    { key: "dividend", label: "红利防御", color: "red" },
                  ].map((cat) => {
                    const val = selectedDateFlow.flows_by_category?.[cat.key];
                    const isPos = (val ?? 0) > 0;
                    const isNeg = (val ?? 0) < 0;
                    return (
                      <Col span={6} key={cat.key}>
                        <div style={{ padding: "8px 10px", borderRadius: 6, border: "1px solid var(--c-border)", background: "var(--c-bg-card)" }}>
                          <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center", marginBottom: 4 }}>
                            <Tag color={cat.color} style={{ margin: 0, fontSize: 10, padding: "0 4px" }}>{cat.label}</Tag>
                          </div>
                          <div style={{ fontFamily: "var(--c-font-mono)", fontWeight: 700, fontSize: 14, color: isPos ? colors.up : isNeg ? colors.down : colors.textPrimary }}>
                            {val != null ? formatSignedFlow(val, "亿") : "-"}
                          </div>
                        </div>
                      </Col>
                    );
                  })}
                </Row>
              </div>
            )}

            {/* 宽基指数资金明细列表 */}
            <div>
              <Text strong style={{ fontSize: 13, marginBottom: 8, display: "block" }}>各宽基资金净申赎明细（降序）</Text>
              <div style={{ display: "flex", flexDirection: "column", gap: 6 }}>
                {HEATMAP_INDICES.map((name) => ({
                  name,
                  val: selectedDateFlow.flows_by_index?.[name] ?? 0,
                  hasData: selectedDateFlow.flows_by_index?.[name] != null,
                }))
                  .sort((a, b) => b.val - a.val)
                  .map((item, idx) => {
                    const isPos = item.val > 0;
                    const isNeg = item.val < 0;
                    return (
                      <div
                        key={item.name}
                        style={{
                          display: "flex",
                          alignItems: "center",
                          justifyContent: "space-between",
                          padding: "5px 10px",
                          borderRadius: 4,
                          background: idx % 2 === 0 ? "var(--c-bg-layout)" : "transparent",
                          fontSize: 12,
                        }}
                      >
                        <Space size={8}>
                          <span style={{ fontFamily: "var(--c-font-mono)", color: colors.textSecondary, width: 16 }}>{idx + 1}</span>
                          <span style={{ fontWeight: 600 }}>{item.name}</span>
                        </Space>
                        <span
                          style={{
                            fontFamily: "var(--c-font-mono)",
                            fontWeight: 700,
                            color: isPos ? colors.up : isNeg ? colors.down : colors.textSecondary,
                          }}
                        >
                          {item.hasData ? formatSignedFlow(item.val, "亿元") : "暂无"}
                        </span>
                      </div>
                    );
                  })}
              </div>
            </div>
          </div>
        </Modal>
      )}
    </Card>
  );
}
