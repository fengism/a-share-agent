import { useCallback, useMemo, useState } from "react";
import { Button, Card, Col, message, Modal, Row, Segmented, Space, Statistic, Table, Tag, Tooltip, Typography } from "antd";
import type { ColumnsType } from "antd/es/table";
import { DownloadOutlined, FallOutlined, InfoCircleOutlined, RiseOutlined, TableOutlined } from "@ant-design/icons";
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
      return { textAlign: "right", fontFamily: "var(--c-font-mono)", color: "var(--c-text-secondary)" };
    }
    const ratio = Math.min(1, Math.max(0.12, Math.abs(val) / maxAbsFlow));
    const isPos = val > 0;
    // 使用红涨绿跌的平滑渐变透明度
    const bg = isPos
      ? `rgba(245, 34, 45, ${0.08 + ratio * 0.42})`
      : `rgba(82, 196, 26, ${0.08 + ratio * 0.42})`;
    const color = isPos ? "var(--c-up)" : "var(--c-down)";

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
  }, [maxAbsFlow]);

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
            className="national-team-heatmap__date-btn"
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
            <span className="national-team-heatmap__help-span">
              宽基合计 <InfoCircleOutlined className="national-team-heatmap__info-icon" />
            </span>
          </Tooltip>
        ),
        dataIndex: "total_flow_100m",
        key: "total_flow_100m",
        width: 110,
        fixed: isMobile ? undefined : "left",
        sorter: (a, b) => (a.total_flow_100m ?? 0) - (b.total_flow_100m ?? 0),
        render: (val: number | null, row) => {
          if (val == null) return <span className="u-text-muted">-</span>;
          const isPos = val > 0;
          return (
            <Tooltip title={`${row.date} 全市场宽基估算净申购合计：${formatSignedFlow(val, "亿元")} (点击下钻)`}>
              <div
                onClick={() => setSelectedDateFlow(row)}
                className={`national-team-heatmap__total-val ${isPos ? "u-text-up" : val < 0 ? "u-text-down" : ""}`}
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
  }, [getCellStyle, isMobile]);

  return (
    <Card
      className="national-team-heatmap-card"
      size="small"
      data-testid="national-team-flow-heatmap-table"
      title={
        <div className="national-team-heatmap__header-top">
          <Space size={8}>
            <TableOutlined className="national-team-heatmap__title-icon" />
            <span className="national-team-heatmap__title-text">宽基日度资金流向热力矩阵</span>
            <Tag color="cyan" className="national-team-heatmap__unit-tag">金额单位：亿元</Tag>
          </Space>
          <div className="national-team-heatmap__header-controls">
            {/* 颜色图例说明 */}
            <div className="national-team-heatmap__legend">
              <span>流出</span>
              <span className="national-team-heatmap__legend-box national-team-heatmap__legend-box--out" />
              <span className="national-team-heatmap__legend-box national-team-heatmap__legend-box--in" />
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
      <div className="national-team-heatmap__footer">
        <span>口径说明：申赎金额估算值 = 当日份额变动 × 收盘价，非交易所逐笔真实结算现金；支持点击表头排序与点击日期下钻明细。</span>
        {asOfDate && <span>截至 {asOfDate}</span>}
      </div>

      {selectedDateFlow && (
        <Modal
          title={
            <Space size={8} align="center">
              <span className="national-team-heatmap__modal-icon">📅</span>
              <span>{selectedDateFlow.date} 宽基资金流向下钻分析</span>
              {selectedDateFlow.benchmark_close != null && (
                <Tag color="blue" className="national-team-heatmap__modal-tag">
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
          <div className="national-team-heatmap__modal-body">
            {/* 核心数据汇总 */}
            <Row gutter={[12, 12]} className="national-team-heatmap__stat-row">
              <Col span={8}>
                <Card size="small" className="national-team-heatmap__stat-card">
                  <Statistic
                    title="当日宽基估算净申购"
                    value={selectedDateFlow.total_flow_100m != null ? `${selectedDateFlow.total_flow_100m > 0 ? "+" : ""}${selectedDateFlow.total_flow_100m.toFixed(2)} 亿元` : "-"}
                    className={`national-team-heatmap__stat ${
                      (selectedDateFlow.total_flow_100m ?? 0) > 0
                        ? "national-team-heatmap__stat--up"
                        : (selectedDateFlow.total_flow_100m ?? 0) < 0
                          ? "national-team-heatmap__stat--down"
                          : ""
                    }`}
                    prefix={(selectedDateFlow.total_flow_100m ?? 0) > 0 ? <RiseOutlined /> : (selectedDateFlow.total_flow_100m ?? 0) < 0 ? <FallOutlined /> : undefined}
                  />
                </Card>
              </Col>
              <Col span={8}>
                <Card size="small" className="national-team-heatmap__stat-card">
                  <Statistic
                    title="样本 ETF 成交额"
                    value={selectedDateFlow.total_amount_100m != null ? `${selectedDateFlow.total_amount_100m.toFixed(1)} 亿元` : "-"}
                    className="national-team-heatmap__stat national-team-heatmap__stat--primary"
                  />
                </Card>
              </Col>
              <Col span={8}>
                <Card size="small" className="national-team-heatmap__stat-card">
                  <Statistic
                    title="区间累计净申购"
                    value={selectedDateFlow.cumulative_flow_100m != null ? `${selectedDateFlow.cumulative_flow_100m > 0 ? "+" : ""}${selectedDateFlow.cumulative_flow_100m.toFixed(1)} 亿元` : "-"}
                    className={`national-team-heatmap__stat ${
                      (selectedDateFlow.cumulative_flow_100m ?? 0) > 0
                        ? "national-team-heatmap__stat--up"
                        : (selectedDateFlow.cumulative_flow_100m ?? 0) < 0
                          ? "national-team-heatmap__stat--down"
                          : ""
                    }`}
                  />
                </Card>
              </Col>
            </Row>

            {/* 板块资金拆解 */}
            {selectedDateFlow.flows_by_category && Object.keys(selectedDateFlow.flows_by_category).length > 0 && (
              <div className="national-team-heatmap__category-section">
                <Text strong className="national-team-heatmap__section-title">战术板块资金拆解</Text>
                <Row gutter={[8, 8]}>
                  {[
                    { key: "core_broad", label: "核心大盘", color: "blue" },
                    { key: "a500", label: "新质A500", color: "gold" },
                    { key: "growth", label: "中小成长", color: "cyan" },
                    { key: "dividend", label: "红利防御", color: "purple" },
                  ].map((cat) => {
                    const val = selectedDateFlow.flows_by_category?.[cat.key];
                    const isPos = (val ?? 0) > 0;
                    const isNeg = (val ?? 0) < 0;
                    return (
                      <Col span={6} key={cat.key}>
                        <div className="national-team-heatmap__cat-card">
                          <div className="national-team-heatmap__cat-header">
                            <Tag color={cat.color} className="national-team-heatmap__cat-tag">{cat.label}</Tag>
                          </div>
                          <div
                            className={`national-team-heatmap__cat-val ${
                              isPos
                                ? "national-team-heatmap__cat-val--up"
                                : isNeg
                                  ? "national-team-heatmap__cat-val--down"
                                  : "national-team-heatmap__cat-val--neutral"
                            }`}
                          >
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
              <Text strong className="national-team-heatmap__section-title">各宽基资金净申赎明细（降序）</Text>
              <div className="national-team-heatmap__index-list">
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
                        className={`national-team-heatmap__index-row ${idx % 2 === 0 ? "national-team-heatmap__index-row--alt" : ""}`}
                      >
                        <Space size={8}>
                          <span className="national-team-heatmap__index-idx">{idx + 1}</span>
                          <span className="national-team-heatmap__index-name">{item.name}</span>
                        </Space>
                        <span
                          className={`national-team-heatmap__index-val ${
                            isPos
                              ? "national-team-heatmap__index-val--up"
                              : isNeg
                                ? "national-team-heatmap__index-val--down"
                                : "national-team-heatmap__index-val--neutral"
                          }`}
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
