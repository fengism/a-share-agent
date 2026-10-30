import { useMemo, useState } from "react";
import {
  Alert,
  Button,
  Card,
  Col,
  Empty,
  Input,
  Modal,
  Row,
  Segmented,
  Space,
  Statistic,
  Table,
  Tag,
  Typography,
  Tooltip,
  message,
} from "antd";
import type { ColumnsType } from "antd/es/table";
import {
  BankOutlined,
  CalendarOutlined,
  DatabaseOutlined,
  DownOutlined,
  DownloadOutlined,
  FallOutlined,
  FullscreenOutlined,
  InfoCircleOutlined,
  ReloadOutlined,
  RiseOutlined,
  SafetyCertificateOutlined,
  SearchOutlined,
  UpOutlined,
} from "@ant-design/icons";
import ReactECharts from "echarts-for-react/lib/core";
import echarts from "../../charts/echarts-setup";
import { useNationalTeamHoldings } from "../../api/queries";
import PreloadLink from "../../components/PreloadLink";
import SectionDataState from "../../components/SectionDataState";
import { useMediaQuery } from "../../hooks/useMediaQuery";
import { useColors } from "../../styles/ui";
import { APP_FONT_FAMILY } from "../../theme/typography";
import { formatNumberWithSeparators } from "../../utils/format";
import { buildStockProfileUrl } from "../../utils/stockLinks";
import { useSearchParams } from "react-router-dom";
import { updateUrlSearchParam, useUrlSearchParam } from "../../hooks/useUrlSearchParam";
import type {
  NationalTeamDailyFlow,
  NationalTeamEtfSeries,
  NationalTeamIndexSeries,
  NationalTeamMilestone,
  NationalTeamPortrait,
  NationalTeamSupportScore,
  NationalTeamSupportZone,
  NationalTeamTopHolding,
} from "../../types/stock";
import { marketDateStamp } from "../../utils/marketTime";
import "./national-team.css";

const { Text, Title } = Typography;
const HISTORY_WINDOWS = [30, 60, 120, 240, 365] as const;
const INDEX_ORDER = [
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
];

const INDEX_TAG_COLORS: Record<string, string> = {
  "沪深300": "blue",
  "上证50": "purple",
  "中证A500": "gold",
  "中证500": "cyan",
  "中证1000": "orange",
  "中证2000": "geekblue",
  "科创50": "volcano",
  "科创100": "magenta",
  "创业板": "green",
  "红利低波": "red",
};

const CATEGORY_TAG_LABELS: Record<string, { label: string; color: string }> = {
  core_broad: { label: "核心大盘", color: "blue" },
  a500: { label: "新质A500", color: "gold" },
  growth: { label: "中小成长", color: "cyan" },
  dividend: { label: "红利防御", color: "red" },
};

const CATEGORY_OPTIONS = [
  { label: "全部板块", value: "all" },
  { label: "核心大盘", value: "core_broad" },
  { label: "新质A500", value: "a500" },
  { label: "中小成长", value: "growth" },
  { label: "红利防御", value: "dividend" },
];

function downloadNationalTeamCsv(etfs: NationalTeamEtfSeries[], asOfDate?: string | null) {
  const headers = [
    "战术分类",
    "宽基板块",
    "ETF代码",
    "ETF名称",
    "基金公司",
    "市场",
    "最新日期",
    "最新份额(亿份)",
    "1日变化(亿份)",
    "5日变化(亿份)",
    "20日变化(亿份)",
    "1日估算净申购(亿元)",
    "成交额(亿元)",
    "量比",
    "放量异动",
  ];

  const escapeCell = (val: unknown) => {
    if (val == null) return "";
    const str = String(val);
    if (str.includes(",") || str.includes('"') || str.includes("\n") || str.includes("\r")) {
      return `"${str.replace(/"/g, '""')}"`;
    }
    return str;
  };

  const rows = etfs.map((item) => {
    const latestPoint = item.points?.[item.points.length - 1];
    const flow1d = latestPoint?.estimated_net_flow_100m;
    const catLabel = CATEGORY_TAG_LABELS[item.category || "core_broad"]?.label || "核心大盘";
    return [
      catLabel,
      item.index_name,
      item.code,
      item.name,
      item.fund_manager || "",
      item.exchange === "SH" ? "上海" : "深圳",
      item.latest_date || "",
      item.latest_shares_100m != null ? item.latest_shares_100m.toFixed(2) : "",
      item.latest_change_1d_100m != null ? item.latest_change_1d_100m.toFixed(2) : "",
      item.change_5d_100m != null ? item.change_5d_100m.toFixed(2) : "",
      item.change_20d_100m != null ? item.change_20d_100m.toFixed(2) : "",
      flow1d != null ? flow1d.toFixed(2) : "",
      item.latest_amount_100m != null ? item.latest_amount_100m.toFixed(2) : "",
      item.volume_ratio != null ? item.volume_ratio.toFixed(2) : "",
      item.is_abnormal_volume ? "显著放量" : "正常",
    ].map(escapeCell).join(",");
  });

  const csvContent = "\uFEFF" + [headers.map(escapeCell).join(","), ...rows].join("\r\n");
  if (typeof window === "undefined" || typeof URL.createObjectURL !== "function") return;
  const blob = new Blob([csvContent], { type: "text/csv;charset=utf-8;" });
  const url = URL.createObjectURL(blob);
  const link = document.createElement("a");
  link.setAttribute("href", url);
  link.setAttribute("download", `国家队ETF监测_${asOfDate || marketDateStamp()}.csv`);
  document.body.appendChild(link);
  link.click();
  document.body.removeChild(link);
  URL.revokeObjectURL(url);
}

function formatShares(value: number | null | undefined) {
  return value == null ? "-" : `${formatNumberWithSeparators(value)} 亿份`;
}

function formatSigned(value: number | null | undefined, unit = "亿份") {
  if (value == null || !Number.isFinite(value)) return "-";
  return `${value > 0 ? "+" : ""}${formatNumberWithSeparators(value)} ${unit}`;
}

function valueColor(value: number | null | undefined, up: string, down: string, neutral: string) {
  if (value == null || value === 0) return neutral;
  return value > 0 ? up : down;
}

function IndexDualAxisChart({ item }: { item: NationalTeamIndexSeries }) {
  const colors = useColors();
  const [expanded, setExpanded] = useState(false);
  const points = useMemo(() => item.points ?? [], [item.points]);
  const showPointMarkers = points.length <= 1;
  const shareColor = colors.info || "#20c6e5";
  const indexColor = colors.warning || "#f59e0b";

  const option = useMemo(() => ({
    animationDuration: 350,
    textStyle: { fontFamily: APP_FONT_FAMILY },
    tooltip: {
      trigger: "axis",
      axisPointer: {
        type: "cross",
        lineStyle: { color: colors.border, type: "dashed" },
        crossStyle: { color: colors.border },
      },
      backgroundColor: colors.elevatedBg,
      borderColor: colors.border,
      borderWidth: 1,
      padding: [8, 12],
      textStyle: { color: colors.textPrimary, fontSize: 12, fontFamily: APP_FONT_FAMILY },
      extraCssText: "box-shadow: 0 8px 24px rgba(0, 0, 0, 0.22); border-radius: 8px; backdrop-filter: blur(8px);",
      formatter: (params: Array<{ axisValueLabel: string; marker: string; seriesName: string; value: number | null; dataIndex: number }>) => {
        if (!params.length) return "";
        const dataIdx = params[0].dataIndex;
        const pt = points[dataIdx];
        const rows = params.map((entry) => {
          const isShare = entry.seriesName === "ETF 合计份额";
          const unit = isShare ? "亿份" : "点";
          const formattedVal = formatNumberWithSeparators(entry.value, 2);
          return `<div style="display:flex;justify-content:space-between;align-items:center;gap:20px;margin-top:4px">
            <span style="display:flex;align-items:center;gap:6px;font-size:12px">${entry.marker}${entry.seriesName}</span>
            <b style="font-family:var(--c-font-mono);font-size:12px">${formattedVal} ${unit}</b>
          </div>`;
        }).join("");

        let flowNote = "";
        if (pt?.shares_change_100m != null) {
          const isSharePos = pt.shares_change_100m > 0;
          const shareChangeColor = pt.shares_change_100m === 0 ? colors.textSecondary : isSharePos ? colors.up : colors.down;
          flowNote += `<div style="display:flex;justify-content:space-between;align-items:center;gap:20px;margin-top:5px;padding-top:4px;border-top:1px dashed ${colors.border};font-size:11px">
            <span style="color:${colors.textSecondary}">单日份额变动</span>
            <span style="font-family:var(--c-font-mono);color:${shareChangeColor};font-weight:600">${formatSigned(pt.shares_change_100m)}</span>
          </div>`;
        }
        if (pt?.estimated_net_flow_100m != null) {
          const isFlowPos = pt.estimated_net_flow_100m > 0;
          const flowColor = pt.estimated_net_flow_100m === 0 ? colors.textSecondary : isFlowPos ? colors.up : colors.down;
          flowNote += `<div style="display:flex;justify-content:space-between;align-items:center;gap:20px;margin-top:3px;font-size:11px">
            <span style="color:${colors.textSecondary}">估算资金净申购</span>
            <span style="font-family:var(--c-font-mono);color:${flowColor};font-weight:600">${formatSigned(pt.estimated_net_flow_100m, "亿元")}</span>
          </div>`;
        }

        return `<div style="font-weight:600;margin-bottom:4px;font-size:12px;color:${colors.textPrimary}">${params[0].axisValueLabel}</div>${rows}${flowNote}`;
      },
    },
    legend: { show: false },
    grid: { left: 52, right: 52, top: 20, bottom: 24 },
    xAxis: {
      type: "category",
      boundaryGap: false,
      data: points.map((point) => point.date),
      axisLabel: { color: colors.textSecondary, hideOverlap: true, fontSize: 10 },
      axisLine: { lineStyle: { color: colors.border } },
    },
    yAxis: [
      {
        type: "value",
        name: "份额（亿份）",
        scale: true,
        nameTextStyle: { color: shareColor, fontSize: 10, fontWeight: 600, padding: [0, 0, 2, 0] },
        axisLabel: { color: colors.textSecondary, fontSize: 10, formatter: (val: number) => formatNumberWithSeparators(val, 1) },
        splitLine: { lineStyle: { color: colors.border, type: "dashed", opacity: 0.35 } },
      },
      {
        type: "value",
        name: "指数（点）",
        scale: true,
        nameTextStyle: { color: indexColor, fontSize: 10, fontWeight: 600, padding: [0, 0, 2, 0] },
        axisLabel: { color: colors.textSecondary, fontSize: 10, formatter: (val: number) => Math.round(val).toLocaleString() },
        splitLine: { show: false },
      },
    ],
    dataZoom: [{ type: "inside", start: 0, end: 100 }],
    series: [
      {
        name: "ETF 合计份额",
        type: "line",
        yAxisIndex: 0,
        smooth: 0.2,
        showSymbol: showPointMarkers,
        symbolSize: 7,
        connectNulls: false,
        data: points.map((point) => point.total_shares_100m),
        lineStyle: { color: shareColor, width: 2.2, type: "solid" },
        itemStyle: { color: shareColor },
        areaStyle: {
          color: {
            type: "linear",
            x: 0,
            y: 0,
            x2: 0,
            y2: 1,
            colorStops: [
              { offset: 0, color: `${shareColor}24` },
              { offset: 0.9, color: `${shareColor}04` },
              { offset: 1, color: `${shareColor}00` },
            ],
          },
        },
        emphasis: { focus: "series" },
      },
      {
        name: `${item.index_name}指数`,
        type: "line",
        yAxisIndex: 1,
        smooth: 0.2,
        showSymbol: showPointMarkers,
        symbolSize: 7,
        connectNulls: false,
        data: points.map((point) => point.index_close),
        lineStyle: { color: indexColor, width: 1.8, type: "dashed" },
        itemStyle: { color: indexColor },
        emphasis: { focus: "series" },
      },
    ],
  }), [colors, indexColor, item.index_name, points, shareColor, showPointMarkers]);

  return (
    <Card className="national-team-index-card" styles={{ body: { padding: "12px 14px 10px" } }}>
      <div className="national-team-index-card__header">
        <div className="national-team-index-card__title-col">
          <div className="national-team-index-card__title-row" style={{ width: "100%", justifyContent: "space-between" }}>
            <Space size={6} align="center">
              <Title level={3} className="national-team-index-card__title">{item.index_name}</Title>
              <Tag color={INDEX_TAG_COLORS[item.index_name] || "default"} className="national-team-index-card__tag">
                {item.index_code}
              </Tag>
            </Space>
            {points.length > 0 && (
              <Button
                type="text"
                size="small"
                aria-label="放大查看大图"
                title="放大查看大图"
                icon={<FullscreenOutlined />}
                onClick={() => setExpanded(true)}
                style={{ color: colors.textSecondary, padding: "0 4px", height: 22 }}
              />
            )}
          </div>
          <div className="national-team-index-card__legend" aria-label={`${item.index_name}图例`}>
            <span className="national-team-index-card__legend-item">
              <span
                aria-hidden="true"
                className="national-team-index-card__legend-line"
                style={{ color: shareColor }}
              />
              ETF 合计份额
              <Text type="secondary" className="national-team-index-card__legend-sub">左轴</Text>
            </span>
            <span className="national-team-index-card__legend-item">
              <span
                aria-hidden="true"
                className="national-team-index-card__legend-line national-team-index-card__legend-line--dashed"
                style={{ color: indexColor }}
              />
              {item.index_name}指数
              <Text type="secondary" className="national-team-index-card__legend-sub">右轴</Text>
            </span>
          </div>
        </div>

        <div className="national-team-index-card__stat-col">
          <div className="national-team-index-card__shares-box">
            <span className="national-team-index-card__shares-label">截至 {item.latest_date || "-"}</span>
            <Text type="secondary">覆盖 {item.covered_etf_codes?.length ?? 0}/{item.etf_codes?.length ?? 0} 只</Text>
            <strong className="national-team-index-card__shares-val">{formatShares(item.latest_total_shares_100m)}</strong>
          </div>
          <Space size={4} className="national-team-index-card__delta-wrap">
            <span
              className="national-team-index-card__change-tag"
              style={{
                color: valueColor(item.latest_change_1d_100m, colors.up, colors.down, colors.textSecondary),
                background: (item.latest_change_1d_100m ?? 0) > 0 ? colors.upBg : (item.latest_change_1d_100m ?? 0) < 0 ? colors.downBg : "transparent",
              }}
            >
              1日 {formatSigned(item.latest_change_1d_100m)}
            </span>
            {item.change_5d_100m != null && (
              <span
                className="national-team-index-card__change-tag"
                style={{
                  color: valueColor(item.change_5d_100m, colors.up, colors.down, colors.textSecondary),
                  background: (item.change_5d_100m ?? 0) > 0 ? colors.upBg : (item.change_5d_100m ?? 0) < 0 ? colors.downBg : "transparent",
                }}
              >
                5日 {formatSigned(item.change_5d_100m)}
              </span>
            )}
          </Space>
        </div>
      </div>

      <div className="national-team-index-card__etfs-bar">
        <Text type="secondary" className="national-team-index-card__etf-list" ellipsis={{ tooltip: item.etf_codes?.join(" · ") }}>
          成分：{item.etf_codes?.join(" · ") || "暂无 ETF"}
        </Text>
      </div>

      {points.length === 1 && (
        <Text type="secondary" className="national-team-index-card__history-note">
          深交所份额历史正在补齐，当前仅有 1 个份额点。
        </Text>
      )}

      {points.length ? (
        <ReactECharts
          echarts={echarts}
          option={option}
          className="national-team-index-card__chart"
          style={{ width: "100%", height: 215 }}
          notMerge
        />
      ) : (
        <Empty image={Empty.PRESENTED_IMAGE_SIMPLE} description="暂无份额与指数历史" style={{ margin: "32px 0" }} />
      )}

      <Modal
        title={`${item.index_name}（${item.index_code}）- 份额与指数走势大图`}
        open={expanded}
        onCancel={() => setExpanded(false)}
        footer={null}
        width={920}
        destroyOnHidden
      >
        <div style={{ padding: "8px 0" }}>
          <ReactECharts
            echarts={echarts}
            option={{
              ...option,
              grid: { left: 56, right: 56, top: 32, bottom: 44 },
              dataZoom: [
                { type: "inside", start: 0, end: 100 },
                { type: "slider", start: 0, end: 100, height: 22, bottom: 8 },
              ],
            }}
            style={{ width: "100%", height: 480 }}
            notMerge
          />
        </div>
      </Modal>
    </Card>
  );
}

function DailyFlowStackedChart({
  dailyFlows,
  milestones,
}: {
  dailyFlows?: NationalTeamDailyFlow[];
  milestones?: NationalTeamMilestone[];
}) {
  const colors = useColors();
  const flows = useMemo(() => dailyFlows ?? [], [dailyFlows]);
  const relevantMilestones = useMemo(() => {
    if (!milestones || !flows.length) return [];
    const dateSet = new Set(flows.map((f) => f.date));
    return milestones.filter((m) => dateSet.has(m.date));
  }, [milestones, flows]);
  if (!flows.length) return null;

  const dates = flows.map((f) => f.date);
  const categories = [
    { key: "core_broad", name: "核心大盘", color: "#1677ff" },
    { key: "a500", name: "新质A500", color: "#faad14" },
    { key: "growth", name: "中小成长", color: "#13c2c2" },
    { key: "dividend", name: "红利防御", color: "#f5222d" },
  ];

  const option = {
    animationDuration: 300,
    textStyle: { fontFamily: APP_FONT_FAMILY },
    tooltip: {
      trigger: "axis",
      axisPointer: { type: "shadow" },
      backgroundColor: colors.elevatedBg,
      borderColor: colors.border,
      borderWidth: 1,
      padding: [8, 12],
      textStyle: { color: colors.textPrimary, fontSize: 12, fontFamily: APP_FONT_FAMILY },
      extraCssText: "box-shadow: 0 8px 24px rgba(0, 0, 0, 0.22); border-radius: 8px; backdrop-filter: blur(8px);",
      formatter: (params: Array<{ seriesName: string; value: number; marker: string }>) => {
        if (!params.length) return "";
        const dataIdx = (params[0] as unknown as { dataIndex: number }).dataIndex;
        const pt = flows[dataIdx];
        const dateStr = pt?.date || "";
        const totalFlow = pt?.total_flow_100m;
        const totalShares = pt?.total_shares_change_100m;
        const totalColor = valueColor(totalFlow, colors.up, colors.down, colors.textPrimary);
        const milestoneHit = relevantMilestones.find((m) => m.date === dateStr);

        let rows = "";
        for (const p of params) {
          if (p.value !== 0 && p.value != null) {
            const pColor = valueColor(p.value, colors.up, colors.down, colors.textPrimary);
            rows += `<div style="display:flex;justify-content:space-between;align-items:center;gap:16px;margin-top:3px;font-size:11px">
              <span style="display:flex;align-items:center;gap:5px">${p.marker}${p.seriesName}</span>
              <b style="font-family:var(--c-font-mono);color:${pColor}">${formatSigned(p.value, "亿元")}</b>
            </div>`;
          }
        }

        const milestoneHtml = milestoneHit
          ? `<div style="margin-top:6px;padding:4px 6px;border-radius:4px;background:rgba(250,173,20,0.12);border:1px solid #faad14;font-size:11px">
              <div style="color:#d48806;font-weight:600">★ 关键救市节点：${milestoneHit.title}</div>
              <div style="color:${colors.textSecondary};margin-top:2px;line-height:1.3">${milestoneHit.description}</div>
            </div>`
          : "";

        return `<div style="font-weight:600;margin-bottom:4px;font-size:12px;color:${colors.textPrimary}">${dateStr}</div>
          <div style="display:flex;justify-content:space-between;align-items:center;gap:16px;margin-bottom:6px;padding-bottom:4px;border-bottom:1px solid ${colors.border};font-size:12px">
            <span>当日宽基净申购合计</span>
            <b style="font-family:var(--c-font-mono);color:${totalColor}">${formatSigned(totalFlow, "亿元")}</b>
          </div>
          ${rows}
          ${totalShares != null ? `<div style="display:flex;justify-content:space-between;align-items:center;gap:16px;margin-top:4px;padding-top:4px;border-top:1px dashed ${colors.border};font-size:11px;color:${colors.textSecondary}">
            <span>当日份额变动合计</span>
            <span style="font-family:var(--c-font-mono)">${formatSigned(totalShares)}</span>
          </div>` : ""}
          ${milestoneHtml}`;
      },
    },
    legend: {
      show: true,
      top: 0,
      right: 12,
      textStyle: { color: colors.textSecondary, fontSize: 11 },
      itemWidth: 10,
      itemHeight: 10,
    },
    grid: { left: 48, right: 24, top: 28, bottom: 32 },
    xAxis: {
      type: "category",
      data: dates,
      axisLabel: { color: colors.textSecondary, hideOverlap: true, fontSize: 10 },
      axisLine: { lineStyle: { color: colors.border } },
    },
    yAxis: {
      type: "value",
      name: "估算净申购（亿元）",
      nameTextStyle: { color: colors.textSecondary, fontSize: 10, padding: [0, 0, 2, 0] },
      axisLabel: {
        color: colors.textSecondary,
        fontSize: 10,
        formatter: (val: number) => formatNumberWithSeparators(val, 1),
      },
      splitLine: { lineStyle: { color: colors.border, type: "dashed", opacity: 0.35 } },
    },
    dataZoom: [
      { type: "inside", start: Math.max(0, 100 - (30 / Math.max(1, dates.length)) * 100), end: 100 },
      { type: "slider", start: Math.max(0, 100 - (30 / Math.max(1, dates.length)) * 100), end: 100, height: 18, bottom: 2 },
    ],
    series: categories.map((cat, idx) => ({
      name: cat.name,
      type: "bar",
      stack: "net_flow",
      itemStyle: { color: cat.color, borderRadius: [2, 2, 0, 0] },
      data: flows.map((f) => f.flows_by_category?.[cat.key] ?? 0),
      markLine: (idx === 0 && relevantMilestones.length > 0) ? {
        symbol: ["none", "none"],
        label: {
          show: true,
          position: "insideEndTop",
          formatter: (p: { name: string }) => `★ ${p.name}`,
          fontSize: 10,
          color: "#faad14",
        },
        lineStyle: {
          color: "#faad14",
          type: "dashed",
          width: 1.5,
        },
        data: relevantMilestones.map((m) => ({
          xAxis: m.date,
          name: m.title,
        })),
      } : undefined,
    })),
  };

  return (
    <Card
      className="national-team-stacked-flow-card"
      size="small"
      title={
        <div style={{ display: "flex", alignItems: "center", gap: 8, flexWrap: "wrap" }}>
          <span style={{ fontWeight: 600, fontSize: 14 }}>全市场宽基每日净申赎走势</span>
          <Text type="secondary" style={{ fontSize: 11 }}>
            各板块每日资金净申购/净赎回估算（亿元）
          </Text>
        </div>
      }
    >
      <div data-testid="national-team-daily-flow-chart">
        <ReactECharts
          echarts={echarts}
          option={option}
          data-testid="national-team-daily-flow-echarts"
          style={{ width: "100%", height: 230 }}
          notMerge
        />
      </div>
    </Card>
  );
}

function SupportScoreRadarCard({ supportScore }: { supportScore?: NationalTeamSupportScore }) {
  const colors = useColors();
  if (!supportScore) return null;

  const score = supportScore.score;
  const statusColors = {
    strong: { bg: "rgba(245, 34, 45, 0.12)", border: "#f5222d", text: "#f5222d", tag: "red" },
    active: { bg: "rgba(250, 140, 22, 0.12)", border: "#fa8c16", text: "#fa8c16", tag: "orange" },
    moderate: { bg: "rgba(22, 119, 255, 0.12)", border: "#1677ff", text: "#1677ff", tag: "blue" },
    neutral: { bg: "rgba(100, 116, 139, 0.12)", border: "#94a3b8", text: "#64748b", tag: "default" },
  }[supportScore.status] || { bg: "transparent", border: colors.border, text: colors.textPrimary, tag: "default" };

  return (
    <Card
      className="national-team-support-radar-card"
      size="small"
      data-testid="national-team-support-radar"
      styles={{ body: { padding: "12px 16px" } }}
    >
      <Row gutter={[16, 12]} align="middle">
        <Col xs={24} md={8} lg={7}>
          <div style={{ display: "flex", alignItems: "center", gap: 14 }}>
            <div
              style={{
                display: "flex",
                flexDirection: "column",
                alignItems: "center",
                justifyContent: "center",
                width: 64,
                height: 64,
                borderRadius: "50%",
                background: statusColors.bg,
                border: `2px solid ${statusColors.border}`,
                boxShadow: `0 0 12px ${statusColors.bg}`,
                flexShrink: 0,
              }}
            >
              <span style={{ fontSize: 20, fontWeight: 700, fontFamily: "var(--c-font-mono)", color: statusColors.text, lineHeight: 1 }}>
                {Math.round(score)}
              </span>
              <span style={{ fontSize: 9, color: colors.textSecondary, marginTop: 2 }}>强度指数</span>
            </div>
            <div>
              <div style={{ display: "flex", alignItems: "center", gap: 6 }}>
                <span style={{ fontWeight: 700, fontSize: 15, color: colors.textPrimary }}>国家队托底雷达</span>
                <Tag color={statusColors.tag} style={{ margin: 0, fontWeight: 600, fontSize: 11 }}>
                  {supportScore.label}
                </Tag>
              </div>
              <Text type="secondary" style={{ fontSize: 11, display: "block", marginTop: 4, lineHeight: 1.4 }}>
                {supportScore.description || "综合测算资金流入、板块覆盖度与抗跌偏离。"}
              </Text>
            </div>
          </div>
        </Col>

        <Col xs={24} md={16} lg={17}>
          <Row gutter={[12, 8]}>
            <Col xs={24} sm={8}>
              <div className="national-team-factor-item">
                <div style={{ display: "flex", justifyContent: "space-between", fontSize: 11, marginBottom: 3 }}>
                  <span style={{ color: colors.textSecondary }}>资金托底因子</span>
                  <span style={{ fontFamily: "var(--c-font-mono)", fontWeight: 600 }}>{supportScore.net_flow_factor} / 40</span>
                </div>
                <div style={{ height: 4, background: "var(--c-border)", borderRadius: 2, overflow: "hidden" }}>
                  <div style={{ height: "100%", width: `${Math.min(100, (supportScore.net_flow_factor / 40) * 100)}%`, background: colors.primary, borderRadius: 2 }} />
                </div>
              </div>
            </Col>
            <Col xs={24} sm={8}>
              <div className="national-team-factor-item">
                <div style={{ display: "flex", justifyContent: "space-between", fontSize: 11, marginBottom: 3 }}>
                  <span style={{ color: colors.textSecondary }}>板块扩散因子</span>
                  <span style={{ fontFamily: "var(--c-font-mono)", fontWeight: 600 }}>{supportScore.breadth_factor} / 30</span>
                </div>
                <div style={{ height: 4, background: "var(--c-border)", borderRadius: 2, overflow: "hidden" }}>
                  <div style={{ height: "100%", width: `${Math.min(100, (supportScore.breadth_factor / 30) * 100)}%`, background: "#13c2c2", borderRadius: 2 }} />
                </div>
              </div>
            </Col>
            <Col xs={24} sm={8}>
              <div className="national-team-factor-item">
                <div style={{ display: "flex", justifyContent: "space-between", fontSize: 11, marginBottom: 3 }}>
                  <span style={{ color: colors.textSecondary }}>逆势抗跌因子</span>
                  <span style={{ fontFamily: "var(--c-font-mono)", fontWeight: 600 }}>{supportScore.divergence_factor} / 30</span>
                </div>
                <div style={{ height: 4, background: "var(--c-border)", borderRadius: 2, overflow: "hidden" }}>
                  <div style={{ height: "100%", width: `${Math.min(100, (supportScore.divergence_factor / 30) * 100)}%`, background: "#faad14", borderRadius: 2 }} />
                </div>
              </div>
            </Col>
          </Row>
        </Col>
      </Row>
    </Card>
  );
}

function MilestoneTimelineBar({ milestones }: { milestones?: NationalTeamMilestone[] }) {
  const colors = useColors();
  const [expanded, setExpanded] = useState(false);
  const items = useMemo(() => milestones ?? [], [milestones]);
  if (!items.length) return null;

  const typeTags: Record<string, { label: string; color: string }> = {
    statement: { label: "官方表态", color: "blue" },
    intervention: { label: "主力扫货", color: "red" },
    policy: { label: "制度发布", color: "gold" },
    liquidity: { label: "流动性落地", color: "purple" },
  };

  return (
    <Card
      className="national-team-milestone-card"
      size="small"
      data-testid="national-team-milestones"
      styles={{ body: { padding: "var(--c-pad-inset, 7px 12px)" } }}
    >
      <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center", marginBottom: expanded ? 8 : 0 }}>
        <div style={{ display: "flex", alignItems: "center", gap: 8, flexWrap: "wrap" }}>
          <SafetyCertificateOutlined style={{ color: colors.primary, fontSize: 14 }} />
          <span style={{ fontWeight: 600, fontSize: 13, color: colors.textPrimary }}>国家队关键政策底救市标尺</span>
          <Text type="secondary" style={{ fontSize: 11 }}>
            历次重要增持公告与流动性托底工具节点
          </Text>
        </div>
        <Button
          type="link"
          size="small"
          onClick={() => setExpanded(!expanded)}
          style={{ padding: "0 4px", fontSize: 12, height: "auto" }}
        >
          {expanded ? <>收起明细 <UpOutlined style={{ fontSize: 10, marginLeft: 2 }} /></> : <>查看历次救市节点 <DownOutlined style={{ fontSize: 10, marginLeft: 2 }} /></>}
        </Button>
      </div>

      {expanded && (
        <div className="national-team-milestone-list" style={{ marginTop: 8 }}>
          <Row gutter={[10, 10]}>
            {items.map((m) => {
              const meta = typeTags[m.type] || { label: "政策", color: "default" };
              return (
                <Col xs={24} sm={12} lg={8} key={m.date}>
                  <div
                    style={{
                      padding: "8px 10px",
                      borderRadius: 6,
                      background: "var(--c-bg-subtle, rgba(128, 128, 128, 0.04))",
                      border: "1px solid var(--c-border)",
                    }}
                  >
                    <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center", marginBottom: 4 }}>
                      <span style={{ fontFamily: "var(--c-font-mono)", fontSize: 11, fontWeight: 600, color: colors.textSecondary }}>
                        {m.date}
                      </span>
                      <Tag color={meta.color} style={{ fontSize: 10, lineHeight: "16px", padding: "0 4px", margin: 0 }}>
                        {meta.label}
                      </Tag>
                    </div>
                    <div style={{ fontWeight: 600, fontSize: 12, color: colors.textPrimary, marginBottom: 2 }}>{m.title}</div>
                    <Text type="secondary" style={{ fontSize: 11, display: "block", lineHeight: 1.4 }}>
                      {m.description}
                    </Text>
                    {m.index_points && Object.keys(m.index_points).length > 0 && (
                      <div style={{ marginTop: 4, display: "flex", gap: 4, flexWrap: "wrap" }}>
                        {Object.entries(m.index_points).map(([idx, pts]) => (
                          <Tag key={idx} color="blue" style={{ fontSize: 10, margin: 0, padding: "0 4px", lineHeight: "16px" }}>
                            {idx}: {pts}
                          </Tag>
                        ))}
                      </div>
                    )}
                  </div>
                </Col>
              );
            })}
          </Row>
        </div>
      )}
    </Card>
  );
}

function SupportZonesCard({ supportZones }: { supportZones?: NationalTeamSupportZone[] }) {
  const colors = useColors();
  const zones = useMemo(() => supportZones ?? [], [supportZones]);
  if (!zones.length) return null;

  return (
    <Card
      className="national-team-support-zones-card"
      size="small"
      data-testid="national-team-support-zones"
      title={
        <div style={{ display: "flex", alignItems: "center", gap: 8, flexWrap: "wrap" }}>
          <span style={{ fontWeight: 600, fontSize: 13 }}>核心指数主力成本中枢与托底点位分布</span>
          <Text type="secondary" style={{ fontSize: 11 }}>
            按各点位区间正净申购资金加权估算托底密集区
          </Text>
        </div>
      }
    >
      <Row gutter={[12, 12]}>
        {zones.map((zone) => {
          const isBufferPos = (zone.cost_buffer_pct ?? 0) >= 0;
          const bufferColor = isBufferPos ? colors.up : colors.down;
          return (
            <Col xs={24} md={8} key={zone.index_key}>
              <div
                style={{
                  padding: "var(--c-pad-inset, 7px 12px)",
                  borderRadius: 8,
                  border: "1px solid var(--c-border)",
                  background: "var(--c-bg-subtle, rgba(128, 128, 128, 0.04))",
                }}
              >
                <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center", marginBottom: 6 }}>
                  <span style={{ fontWeight: 600, fontSize: 13 }}>{zone.index_name}</span>
                  <Tag color="blue" style={{ margin: 0, fontSize: 11 }}>
                    当前点位 {zone.current_price ? Math.round(zone.current_price) : "-"}
                  </Tag>
                </div>
                <div style={{ display: "flex", justifyContent: "space-between", alignItems: "baseline", marginBottom: 8 }}>
                  <div>
                    <span style={{ fontSize: 11, color: colors.textSecondary }}>加权平均买入成本：</span>
                    <strong style={{ fontFamily: "var(--c-font-mono)", fontSize: 14, color: colors.textPrimary }}>
                      {zone.weighted_avg_cost ? Math.round(zone.weighted_avg_cost) : "-"} 点
                    </strong>
                  </div>
                  {zone.cost_buffer_pct != null && (
                    <span style={{ fontSize: 11, color: bufferColor, fontWeight: 600 }}>
                      安全垫 {isBufferPos ? "+" : ""}{zone.cost_buffer_pct}%
                    </span>
                  )}
                </div>

                <div style={{ display: "flex", flexDirection: "column", gap: 4 }}>
                  {(zone.zones ?? []).map((z) => (
                    <div key={z.range_label} style={{ display: "flex", alignItems: "center", gap: 8, fontSize: 11 }}>
                      <span style={{ width: 68, color: colors.textSecondary, flexShrink: 0, fontFamily: "var(--c-font-mono)" }}>
                        {z.range_label}
                      </span>
                      <div style={{ flex: 1, height: 6, background: "var(--c-border)", borderRadius: 3, overflow: "hidden" }}>
                        <div
                          style={{
                            height: "100%",
                            width: `${Math.min(100, Math.max(5, z.share_pct))}%`,
                            background: "linear-gradient(90deg, #1677ff88, #1677ff)",
                            borderRadius: 3,
                          }}
                        />
                      </div>
                      <span style={{ width: 44, textAlign: "right", fontFamily: "var(--c-font-mono)", color: colors.textSecondary, flexShrink: 0 }}>
                        {z.share_pct}%
                      </span>
                      <span style={{ width: 55, textAlign: "right", fontFamily: "var(--c-font-mono)", color: colors.textPrimary, flexShrink: 0 }}>
                        {z.net_flow_100m}亿
                      </span>
                    </div>
                  ))}
                </div>
              </div>
            </Col>
          );
        })}
      </Row>
    </Card>
  );
}

function downloadPortraitCsv(portrait: NationalTeamPortrait) {
  const escapeCell = (val: unknown) => {
    if (val == null) return "";
    const str = String(val);
    if (str.includes(",") || str.includes('"') || str.includes("\n") || str.includes("\r")) {
      return `"${str.replace(/"/g, '""')}"`;
    }
    return str;
  };

  const lines: string[] = [];
  lines.push("国家队战略机构底仓全景数据");
  lines.push(`披露口径,${portrait.reporting_period || ""}`);
  lines.push(`预估战略总持股市值(万亿元),${portrait.total_market_value_trillion || ""}`);
  lines.push("");

  // 1. 机构主体
  lines.push("机构主体,机构简称,职能定位,预估规模(万亿元),配置核心");
  for (const e of portrait.entities ?? []) {
    lines.push([e.name, e.short_name, e.role, e.estimated_aum_trillion, e.focus].map(escapeCell).join(","));
  }
  lines.push("");

  // 2. 行业配置
  lines.push("行业板块,配置权重(%),持股市值(亿元),代表性标的");
  for (const a of portrait.industry_allocations ?? []) {
    lines.push([a.industry, a.weight_pct, a.market_value_100m, (a.representative_stocks ?? []).join(" / ")].map(escapeCell).join(","));
  }
  lines.push("");

  // 3. 前十大重仓
  lines.push("排名,标的代码,标的名称,持股主体,所属行业,占总股本比(%),持股市值(亿元)");
  (portrait.top_holdings ?? []).forEach((h, idx) => {
    lines.push([idx + 1, h.code, h.name, h.holder_name, h.industry, h.shareholding_ratio_pct, h.market_value_100m].map(escapeCell).join(","));
  });

  const csvContent = "\uFEFF" + lines.join("\r\n");
  if (typeof window === "undefined" || typeof URL.createObjectURL !== "function") return;
  const blob = new Blob([csvContent], { type: "text/csv;charset=utf-8;" });
  const url = URL.createObjectURL(blob);
  const link = document.createElement("a");
  link.setAttribute("href", url);
  link.setAttribute("download", `国家队战略底仓画像_${marketDateStamp()}.csv`);
  document.body.appendChild(link);
  link.click();
  document.body.removeChild(link);
  URL.revokeObjectURL(url);
}

function NationalTeamPortraitPanel({ portrait }: { portrait?: NationalTeamPortrait }) {
  const colors = useColors();
  const isMobile = useMediaQuery("(max-width: 640px)");
  const p = portrait;
  if (!p) return null;

  const topHoldingsColumns: ColumnsType<NationalTeamTopHolding> = [
    {
      title: "排名",
      key: "rank",
      width: 55,
      align: "center",
      render: (_, __, index) => (
        <span
          className={`national-team-rotation__rank ${index < 3 ? `national-team-rotation__rank--${index + 1}` : ""}`}
          style={{ width: 22, height: 22, lineHeight: "22px", fontSize: 11, display: "inline-block" }}
        >
          {index + 1}
        </span>
      ),
    },
    {
      title: "标的",
      key: "stock",
      width: isMobile ? 130 : 180,
      render: (_, item) => (
        <div style={{ display: "flex", flexDirection: "column" }}>
          <PreloadLink
            to={buildStockProfileUrl(item.code)}
            className="national-team-code national-team-code-link"
            style={{ fontWeight: 600, color: colors.primary }}
          >
            {item.name}
          </PreloadLink>
          <span style={{ fontSize: 11, color: colors.textSecondary, fontFamily: "var(--c-font-mono)" }}>
            {item.code}
          </span>
        </div>
      ),
    },
    {
      title: "持股主体",
      dataIndex: "holder_name",
      key: "holder_name",
      width: isMobile ? 95 : 130,
      render: (val: string) => (
        <Tag color="blue" style={{ fontSize: 11, margin: 0 }}>
          {val}
        </Tag>
      ),
    },
    {
      title: "行业板块",
      dataIndex: "industry",
      key: "industry",
      width: isMobile ? 85 : 120,
      render: (val: string) => (
        <Tag color="cyan" style={{ fontSize: 11, margin: 0 }}>
          {val}
        </Tag>
      ),
    },
    {
      title: "占总股本比",
      dataIndex: "shareholding_ratio_pct",
      key: "shareholding_ratio_pct",
      width: isMobile ? 90 : 110,
      align: "right",
      render: (val: number) => (
        <strong style={{ fontFamily: "var(--c-font-mono)", fontSize: 13, color: colors.textPrimary }}>
          {val.toFixed(2)}%
        </strong>
      ),
    },
    {
      title: "持股市值 (参考)",
      dataIndex: "market_value_100m",
      key: "market_value_100m",
      width: isMobile ? 105 : 140,
      align: "right",
      render: (val: number) => (
        <span style={{ fontFamily: "var(--c-font-mono)", fontSize: 12, color: colors.textSecondary }}>
          {formatNumberWithSeparators(Math.round(val))} 亿元
        </span>
      ),
    },
  ];

  return (
    <div className="national-team-portrait-panel" data-testid="national-team-portrait-panel">
      {/* 实体概览 */}
      <div style={{ marginBottom: 12 }}>
        <Row gutter={[10, 10]}>
          {(p.entities ?? []).map((entity) => (
            <Col xs={24} md={8} key={entity.short_name}>
              <Card
                size="small"
                className="national-team-entity-card"
                title={
                  <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center" }}>
                    <span style={{ fontWeight: 600, fontSize: 13 }}>{entity.short_name}</span>
                    <Tag color="purple" style={{ margin: 0, fontSize: 11 }}>
                      预估规模约 {entity.estimated_aum_trillion} 万亿
                    </Tag>
                  </div>
                }
              >
                <div style={{ fontSize: 12, marginBottom: 6, color: colors.textPrimary, lineHeight: 1.5 }}>
                  <Text strong>职能定位：</Text>{entity.role}
                </div>
                <div style={{ fontSize: 12, color: colors.textSecondary, lineHeight: 1.5 }}>
                  <Text strong>配置核心：</Text>{entity.focus}
                </div>
              </Card>
            </Col>
          ))}
        </Row>
      </div>

      {/* 行业配置分布 */}
      <Card
        size="small"
        className="national-team-industry-card"
        title={
          <div style={{ display: "flex", alignItems: "center", justifyContent: "space-between", flexWrap: "wrap", gap: 8 }}>
            <span style={{ fontWeight: 600, fontSize: 13 }}>国家队战略底仓行业配置与权重分布</span>
            <span style={{ fontSize: 11, color: colors.textSecondary }}>
              披露口径：{p.reporting_period} · 总市值约 {p.total_market_value_trillion} 万亿元
            </span>
          </div>
        }
        style={{ marginBottom: 12 }}
      >
        <Row gutter={[12, 12]}>
          {(p.industry_allocations ?? []).map((alloc) => (
            <Col xs={24} sm={12} md={8} key={alloc.industry}>
              <div
                style={{
                  padding: "var(--c-pad-inset, 7px 12px)",
                  borderRadius: 8,
                  border: "1px solid var(--c-border)",
                  background: "var(--c-bg-subtle, rgba(128, 128, 128, 0.04))",
                }}
              >
                <div style={{ display: "flex", justifyContent: "space-between", alignItems: "baseline", marginBottom: 6 }}>
                  <span style={{ fontWeight: 600, fontSize: 13, color: colors.textPrimary }}>{alloc.industry}</span>
                  <strong style={{ fontFamily: "var(--c-font-mono)", fontSize: 14, color: colors.primary }}>
                    {alloc.weight_pct}%
                  </strong>
                </div>
                <div style={{ height: 6, background: "var(--c-border)", borderRadius: 3, overflow: "hidden", marginBottom: 8 }}>
                  <div
                    style={{
                      height: "100%",
                      width: `${Math.min(100, alloc.weight_pct * 2)}%`,
                      background: "linear-gradient(90deg, #1677ff88, #1677ff)",
                      borderRadius: 3,
                    }}
                  />
                </div>
                <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center", fontSize: 11, color: colors.textSecondary, marginBottom: 6 }}>
                  <span>持股市值约</span>
                  <span style={{ fontFamily: "var(--c-font-mono)" }}>{formatNumberWithSeparators(Math.round(alloc.market_value_100m))} 亿元</span>
                </div>
                <div style={{ display: "flex", flexWrap: "wrap", gap: 4 }}>
                  {(alloc.representative_stocks ?? []).map((stock) => (
                    <Tag key={stock} style={{ fontSize: 10, lineHeight: "16px", padding: "0 4px", margin: 0 }}>
                      {stock}
                    </Tag>
                  ))}
                </div>
              </div>
            </Col>
          ))}
        </Row>
      </Card>

      {/* 十大核心重仓股 */}
      <Card
        size="small"
        className="national-team-top-holdings-card"
        title={
          <div style={{ display: "flex", alignItems: "center", justifyContent: "space-between", flexWrap: "wrap", gap: 8 }}>
            <span style={{ fontWeight: 600, fontSize: 13 }}>核心压舱石标的 · 汇金 / 证金 / 社保前十大战略重仓</span>
            <Text type="secondary" style={{ fontSize: 11 }}>
              上市企业定期报告十大股东口径
            </Text>
          </div>
        }
        extra={
          <Button
            size="small"
            icon={<DownloadOutlined />}
            onClick={() => {
              downloadPortraitCsv(p);
              message.success("已导出国家队战略底仓画像全景数据");
            }}
          >
            导出画像 CSV
          </Button>
        }
      >
        <Table<NationalTeamTopHolding>
          rowKey="code"
          size="small"
          columns={topHoldingsColumns}
          dataSource={p.top_holdings}
          pagination={false}
          scroll={{ x: 600 }}
        />
      </Card>
    </div>
  );
}

export default function NationalTeam() {
  const colors = useColors();
  const isMobile = useMediaQuery("(max-width: 640px)");
  const [, setSearchParams] = useSearchParams();
  const [daysParam, setDaysParam] = useUrlSearchParam("days", "120", {
    allowedValues: ["30", "60", "120", "240", "365"],
  });
  const days = Number(daysParam) as (typeof HISTORY_WINDOWS)[number];

  const [view, setView] = useUrlSearchParam("view", "etf", {
    allowedValues: ["etf", "portrait"],
  });

  const [category] = useUrlSearchParam("category", "all", {
    allowedValues: ["all", "core_broad", "a500", "growth", "dividend"],
  });

  const [rotationWindowParam, setRotationWindowParam] = useUrlSearchParam("rotation", "20", {
    allowedValues: ["20", "5", "1"],
  });
  const rotationWindow = Number(rotationWindowParam) as 20 | 5 | 1;

  const [selectedFilterIndex, setSelectedFilterIndex] = useUrlSearchParam("index", "ALL");
  const [searchKeyword, setSearchKeyword] = useState<string>("");
  const [showPartialDetails, setShowPartialDetails] = useState<boolean>(false);
  const { data, isLoading, isFetching, error, refetch } = useNationalTeamHoldings(days);

  const indices = useMemo(() => [...(data?.indices ?? [])].sort(
    (a, b) => INDEX_ORDER.indexOf(a.index_name) - INDEX_ORDER.indexOf(b.index_name),
  ), [data?.indices]);

  const filteredIndices = useMemo(() => {
    if (category === "all") return indices;
    return indices.filter((item) => (item.category ?? "core_broad") === category);
  }, [category, indices]);

  const etfs = useMemo(() => data?.etfs ?? [], [data?.etfs]);
  const hasData = indices.length > 0 || etfs.length > 0;
  const abnormalEtfs = useMemo(() => etfs.filter((item) => item.is_abnormal_volume), [etfs]);

  const categoryEtfs = useMemo(() => {
    if (category === "all") return etfs;
    return etfs.filter((item) => (item.category ?? "core_broad") === category);
  }, [category, etfs]);

  const rotation = useMemo(() => {
    const getVal = (item: NationalTeamIndexSeries) => {
      if (rotationWindow === 1) return item.latest_change_1d_100m;
      if (rotationWindow === 5) return item.change_5d_100m;
      return item.change_20d_100m;
    };
    const targetIndices = category === "all" ? indices : indices.filter((item) => (item.category ?? "core_broad") === category);
    return [...targetIndices].sort(
      (a, b) => (getVal(b) ?? Number.NEGATIVE_INFINITY) - (getVal(a) ?? Number.NEGATIVE_INFINITY),
    );
  }, [category, indices, rotationWindow]);

  const maxAbsRotation = useMemo(() => {
    const getVal = (item: NationalTeamIndexSeries) => {
      if (rotationWindow === 1) return item.latest_change_1d_100m;
      if (rotationWindow === 5) return item.change_5d_100m;
      return item.change_20d_100m;
    };
    const vals = rotation.map((item) => Math.abs(getVal(item) ?? 0));
    return Math.max(...vals, 0.01);
  }, [rotation, rotationWindow]);

  const filteredEtfs = useMemo(() => {
    let result = categoryEtfs;
    if (selectedFilterIndex !== "ALL") {
      result = result.filter((item) => item.index_name === selectedFilterIndex);
    }
    if (searchKeyword.trim()) {
      const kw = searchKeyword.trim().toLowerCase();
      result = result.filter(
        (item) =>
          item.code.toLowerCase().includes(kw) ||
          item.name.toLowerCase().includes(kw) ||
          item.fund_manager.toLowerCase().includes(kw) ||
          item.index_name.toLowerCase().includes(kw),
      );
    }
    return result;
  }, [categoryEtfs, searchKeyword, selectedFilterIndex]);

  const filterOptions = useMemo(() => [
    { label: `全部 (${categoryEtfs.length})`, value: "ALL" },
    ...INDEX_ORDER.filter((name) => categoryEtfs.some((e) => e.index_name === name)).map((name) => ({
      label: `${name} (${categoryEtfs.filter((e) => e.index_name === name).length})`,
      value: name,
    })),
  ], [categoryEtfs]);

  const handleCategoryChange = (newCat: string) => {
    setSearchParams((current) => {
      const next = updateUrlSearchParam(current, "category", newCat, "all");
      return updateUrlSearchParam(next, "index", "ALL", "ALL");
    });
  };

  const columns: ColumnsType<NationalTeamEtfSeries> = useMemo(() => [
    {
      title: "宽基",
      dataIndex: "index_name",
      key: "index_name",
      width: isMobile ? 85 : 120,
      fixed: isMobile ? undefined : "left",
      render: (name: string, item: NationalTeamEtfSeries) => {
        const catMeta = CATEGORY_TAG_LABELS[item.category ?? "core_broad"];
        return (
          <div style={{ display: "flex", flexDirection: "column", gap: 2 }}>
            <Tag color={INDEX_TAG_COLORS[name] || "default"} className="national-team-index-tag">
              {name}
            </Tag>
            {catMeta && (
              <Tag color={catMeta.color} style={{ fontSize: 10, lineHeight: "16px", padding: "0 4px", margin: 0, width: "fit-content" }}>
                {catMeta.label}
              </Tag>
            )}
          </div>
        );
      },
    },
    {
      title: "ETF",
      key: "etf",
      width: isMobile ? 130 : 210,
      fixed: isMobile ? undefined : "left",
      render: (_, item) => (
        <div className="national-team-etf-name">
          <div className="national-team-etf-code-row">
            <PreloadLink
              to={buildStockProfileUrl(item.code)}
              className="national-team-code national-team-code-link financial-num"
              title={`查看 ${item.name}（${item.code}）行情`}
            >
              {item.code}
            </PreloadLink>
            <Tag className="national-team-exchange-tag">
              {item.exchange === "SH" ? "沪" : "深"}
            </Tag>
          </div>
          <Text type="secondary" className="national-team-etf-fullname" ellipsis title={item.name}>
            {item.name}
          </Text>
        </div>
      ),
    },
    {
      title: "最新份额",
      dataIndex: "latest_shares_100m",
      key: "latest_shares_100m",
      width: isMobile ? 95 : 125,
      align: "right",
      sorter: (a, b) => (a.latest_shares_100m ?? 0) - (b.latest_shares_100m ?? 0),
      render: (value) => (
        <span className="national-team-shares-val">{formatShares(value)}</span>
      ),
    },
    ...([1, 5, 20] as const).map((window): ColumnsType<NationalTeamEtfSeries>[number] => {
      const key = window === 1 ? "latest_change_1d_100m" : (`change_${window}d_100m` as const);
      return {
        title: `${window} 日变化`,
        key,
        width: isMobile ? 85 : 115,
        align: "right",
        sorter: (a, b) => (a[key] ?? 0) - (b[key] ?? 0),
        render: (_, item) => {
          const value = item[key];
          const color = valueColor(value, colors.up, colors.down, colors.textSecondary);
          const bg = (value ?? 0) > 0 ? colors.upBg : (value ?? 0) < 0 ? colors.downBg : "transparent";
          return (
            <span className="national-team-delta-pill" style={{ color, background: bg }}>
              {formatSigned(value)}
            </span>
          );
        },
      };
    }),
    {
      title: "1日估算净申购",
      key: "estimated_net_flow_1d",
      width: isMobile ? 110 : 130,
      align: "right",
      sorter: (a, b) => {
        const flowA = a.points?.[a.points.length - 1]?.estimated_net_flow_100m ?? 0;
        const flowB = b.points?.[b.points.length - 1]?.estimated_net_flow_100m ?? 0;
        return flowA - flowB;
      },
      render: (_, item) => {
        const latestPoint = item.points?.[item.points.length - 1];
        const flow = latestPoint?.estimated_net_flow_100m;
        const color = valueColor(flow, colors.up, colors.down, colors.textSecondary);
        const bg = (flow ?? 0) > 0 ? colors.upBg : (flow ?? 0) < 0 ? colors.downBg : "transparent";
        return (
          <span className="national-team-delta-pill" style={{ color, background: bg }}>
            {formatSigned(flow, "亿元")}
          </span>
        );
      },
    },
    {
      title: "成交额",
      dataIndex: "latest_amount_100m",
      key: "latest_amount_100m",
      width: isMobile ? 85 : 105,
      align: "right",
      sorter: (a, b) => (a.latest_amount_100m ?? 0) - (b.latest_amount_100m ?? 0),
      render: (value: number | null | undefined) => (
        <span className="financial-num" style={{ fontFamily: "var(--c-font-mono)", fontSize: 12 }}>
          {value != null ? `${value.toFixed(1)}亿` : "-"}
        </span>
      ),
    },
    {
      title: "量比",
      dataIndex: "volume_ratio",
      key: "volume_ratio",
      width: isMobile ? 85 : 100,
      align: "right",
      sorter: (a, b) => (a.volume_ratio ?? 0) - (b.volume_ratio ?? 0),
      render: (value: number | null | undefined, item: NationalTeamEtfSeries) => {
        if (value == null) return <span style={{ color: colors.textSecondary }}>-</span>;
        if (item.is_abnormal_volume) {
          return (
            <Tooltip title={`5日均量放大至 ${value} 倍，触发显著异动放量`}>
              <Tag color="volcano" style={{ margin: 0, fontSize: 11, fontWeight: 600, padding: "0 4px" }}>
                放量 {value}x
              </Tag>
            </Tooltip>
          );
        }
        return (
          <span className="financial-num" style={{ fontFamily: "var(--c-font-mono)", fontSize: 12 }}>
            {value.toFixed(2)}x
          </span>
        );
      },
    },
    {
      title: "基金公司",
      dataIndex: "fund_manager",
      key: "fund_manager",
      width: isMobile ? 95 : 110,
      render: (val: string) => <Text className="national-team-subtle-text">{val || "-"}</Text>,
    },
    {
      title: "最新日期",
      dataIndex: "latest_date",
      key: "latest_date",
      width: isMobile ? 90 : 100,
      render: (value, item) => {
        const point = item.points?.find((entry) => entry.date === value);
        const source = point?.source === "sse_history" ? "上交所历史份额"
          : point?.source === "szse_history" ? "深交所历史份额" : point?.source || "未知";
        return (
          <Tooltip title={`来源：${source}；业务日期：${value || "未知"}；抓取时间：${point?.fetched_at || "未知"}；${point?.verification_status === "verified" ? "日期已确认" : "待确认"}`}>
            <span className="national-team-date">{value || "-"}</span>
          </Tooltip>
        );
      },
    },
  ], [colors, isMobile]);

  return (
    <section className="national-team-page" aria-labelledby="national-team-title">
      {/* 头部控制栏：精简流线型高光控制栏 */}
      <header className="national-team-hero">
        <div className="national-team-hero__brand">
          <div className="national-team-hero__icon">
            <BankOutlined />
          </div>
          <div className="national-team-hero__title-wrap">
            <div className="national-team-hero__title-row">
              <Title id="national-team-title" level={1} className="national-team-hero__title">国家队</Title>
              <Tag color="blue" className="national-team-hero__tag">宽基 ETF 监测</Tag>
              <span className="national-team-hero__as-of">
                <CalendarOutlined style={{ marginRight: 4 }} />
                截至 <strong>{data?.as_of_date || "-"}</strong>
              </span>
            </div>
            <div className="national-team-hero__meta">
              <span className="national-team-hero__meta-item">
                <DatabaseOutlined style={{ marginRight: 4 }} />
                数据源：{data?.source || "上交所 / 深交所 / 东方财富"}
              </span>
              <span className="national-team-hero__meta-dot">·</span>
              <span className="national-team-hero__meta-item">
                覆盖 {data?.total_etf_count ?? etfs.length ?? 22} 只核心宽基 ETF
              </span>
            </div>
          </div>
        </div>

        <div className="national-team-hero__controls">
          <Segmented
            aria-label="历史区间"
            value={days}
            options={HISTORY_WINDOWS.map((value) => ({ label: `${value} 天`, value }))}
            onChange={(value) => setDaysParam(String(value))}
            className="national-team-segmented"
          />
          <Button
            type="primary"
            ghost
            icon={<ReloadOutlined spin={isFetching} />}
            loading={isFetching}
            onClick={() => refetch()}
            className="national-team-refresh-btn"
          >
            刷新
          </Button>
        </div>
      </header>

      {/* 警示与说明区域：轻量通透的提示条 */}
      <div className="national-team-alerts">
        <Alert
          className="national-team-disclaimer"
          type="info"
          showIcon
          icon={<InfoCircleOutlined />}
          title="代理口径说明"
          description={data?.disclaimer || "ETF 份额变化仅作为资金行为代理指标，不等于中央汇金真实持仓或实际交易。"}
        />

        {data?.partial && (
          <Alert
            className="national-team-partial-alert"
            type="warning"
            showIcon
            title={
              <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center", width: "100%" }}>
                <span>{data.refreshing ? "数据不完整 · 后台更新中" : "数据不完整"}</span>
                <Button
                  type="link"
                  size="small"
                  onClick={() => setShowPartialDetails((prev) => !prev)}
                  style={{ padding: "0 4px", fontSize: 12, height: "auto" }}
                >
                  {showPartialDetails ? (
                    <>收起明细 <UpOutlined style={{ fontSize: 10, marginLeft: 2 }} /></>
                  ) : (
                    <>查看明细 <DownOutlined style={{ fontSize: 10, marginLeft: 2 }} /></>
                  )}
                </Button>
              </div>
            }
            description={
              showPartialDetails ? (
                <div style={{ marginTop: 4 }}>
                  {[
                    data.stale ? `份额截至 ${data.as_of_date || "未知"}，预期交易日 ${data.expected_date || "待确认"}。` : "",
                    data.calendar_degraded ? "交易日历暂不可用，新鲜度与区间完整性待确认。" : "",
                    data.missing_share_etfs?.length ? `份额缺失或区间不完整：${data.missing_share_etfs.join("、")}。` : "",
                    data.missing_price_etfs?.length ? `ETF 行情缺失：${data.missing_price_etfs.join("、")}。` : "",
                    data.missing_indices?.length ? `指数行情缺失：${data.missing_indices.map((key) => data.indices?.find((item) => item.index_key === key)?.index_name || key).join("、")}。` : "",
                    data.observations?.length ? "无业务日期的当前份额仅作未确认观察，不计入历史与资金估算。" : "",
                    "汇总仅覆盖截至日有份额数据的 ETF；变化按相同标的、相同交易日比较，无法计算时显示“-”，不代表零变化。请谨慎解读。",
                  ].join("")}
                </div>
              ) : (
                <div>
                  {[
                    data.stale ? `份额截至 ${data.as_of_date || "未知"}，预期交易日 ${data.expected_date || "待确认"}。` : "",
                    data.calendar_degraded ? "交易日历暂不可用。" : "",
                    data.missing_share_etfs?.length ? `${data.missing_share_etfs.length} 只 ETF 份额待同步。` : "",
                    data.missing_price_etfs?.length ? `${data.missing_price_etfs.length} 只 ETF 行情待同步。` : "",
                    data.missing_indices?.length ? `${data.missing_indices.length} 个指数行情待同步。` : "",
                    data.observations?.length ? "无业务日期的当前份额仅作未确认观察。" : "",
                  ].filter(Boolean).join(" ") || "部分标的行情或份额正在后台回填中，暂不影响整体观察。"}
                </div>
              )
            }
          />
        )}

        {abnormalEtfs.length > 0 && (
          <Alert
            className="national-team-sweep-alert"
            type="error"
            showIcon
            style={{ borderRadius: 8 }}
            title={
              <div style={{ display: "flex", alignItems: "center", gap: 6, flexWrap: "wrap" }}>
                <span style={{ fontWeight: 600 }}>盘中主力放量异动监测</span>
                <Tag color="volcano" style={{ margin: 0, fontWeight: 600, fontSize: 11 }}>
                  {abnormalEtfs.length} 只 ETF 显著放量
                </Tag>
                <span style={{ fontSize: 12, color: colors.textSecondary }}>
                  （5日量比 ≥ 1.8x 且最新成交额 ≥ 5亿元，疑似主力集中扫货）
                </span>
              </div>
            }
            description={
              <div style={{ display: "flex", flexWrap: "wrap", gap: 8, marginTop: 4 }}>
                {abnormalEtfs.map((item) => (
                  <Tag
                    key={item.code}
                    color="volcano"
                    style={{ cursor: "pointer", padding: "2px 8px", fontSize: 12 }}
                    onClick={() => {
                      setSelectedFilterIndex(item.index_name);
                      setSearchKeyword(item.code);
                    }}
                    title={`点击定位筛选 ${item.name}`}
                  >
                    <strong>{item.name}</strong> ({item.code}) · 成交额 {item.latest_amount_100m?.toFixed(1)}亿 · 量比 {item.volume_ratio}x
                  </Tag>
                ))}
              </div>
            }
          />
        )}
      </div>

      <SectionDataState
        isLoading={isLoading && !hasData}
        error={hasData ? undefined : error}
        onRetry={() => refetch()}
        isEmpty={!isLoading && !error && !hasData}
        emptyText="暂无国家队 ETF 代理监测数据"
        errorTitle="国家队数据加载失败"
        minHeight={420}
        skeletonRows={8}
      >
        {/* 持仓双视角切换栏 */}
        <div className="national-team-view-switcher" style={{ marginBottom: 12 }}>
          <Segmented
            size="middle"
            value={view}
            options={[
              { label: "宽基 ETF 监测 (流动性与申赎)", value: "etf" },
              { label: "战略机构底仓全景 (汇金/证金/社保)", value: "portrait" },
            ]}
            onChange={(val) => setView(String(val))}
            className="national-team-segmented"
            data-testid="national-team-view-switcher"
          />
        </div>

        {view === "portrait" ? (
          <NationalTeamPortraitPanel portrait={data?.portrait} />
        ) : (
          <>
            {/* 国家队托底护盘强度雷达 */}
            {data?.support_score && (
              <div style={{ marginBottom: 10 }}>
                <SupportScoreRadarCard supportScore={data.support_score} />
              </div>
            )}

        {/* KPI 统计控制台：主次分明、轻盈降噪的高端金融终端布局 */}
        <div className="national-team-summary-section">
          <Row gutter={[10, 10]} className="national-team-summary">
            {/* 核心资产总额卡片 */}
            <Col xs={24} sm={12} lg={4}>
              <Card className="national-team-summary__card national-team-summary__card--total">
                <Statistic
                  title="ETF 总份额"
                  value={formatShares(data?.summary?.total_shares_100m)}
                />
                <div className="national-team-summary__hint">覆盖 {data?.covered_etf_count ?? 0}/{data?.total_etf_count ?? 22} 只宽基 ETF · 截至 {data?.as_of_date || "-"}</div>
              </Card>
            </Col>

            {/* 时序份额变动指标组 */}
            <Col xs={12} sm={6} lg={4}>
              <Card
                className="national-team-summary__card"
                style={{
                  borderTop: (data?.summary?.change_1d_100m ?? 0) !== 0
                    ? `2px solid ${valueColor(data?.summary?.change_1d_100m, colors.up, colors.down, colors.border)}`
                    : undefined,
                }}
              >
                <Statistic
                  title="1 日份额变化"
                  value={formatSigned(data?.summary?.change_1d_100m)}
                  prefix={(data?.summary?.change_1d_100m ?? 0) > 0 ? <RiseOutlined /> : (data?.summary?.change_1d_100m ?? 0) < 0 ? <FallOutlined /> : undefined}
                  styles={{ content: { color: valueColor(data?.summary?.change_1d_100m, colors.up, colors.down, colors.textPrimary) } }}
                />
                <div className="national-team-summary__hint">较上一交易日</div>
              </Card>
            </Col>

            <Col xs={12} sm={6} lg={4}>
              <Card
                className="national-team-summary__card"
                style={{
                  borderTop: (data?.summary?.change_5d_100m ?? 0) !== 0
                    ? `2px solid ${valueColor(data?.summary?.change_5d_100m, colors.up, colors.down, colors.border)}`
                    : undefined,
                }}
              >
                <Statistic
                  title="5 日份额变化"
                  value={formatSigned(data?.summary?.change_5d_100m)}
                  prefix={(data?.summary?.change_5d_100m ?? 0) > 0 ? <RiseOutlined /> : (data?.summary?.change_5d_100m ?? 0) < 0 ? <FallOutlined /> : undefined}
                  styles={{ content: { color: valueColor(data?.summary?.change_5d_100m, colors.up, colors.down, colors.textPrimary) } }}
                />
                <div className="national-team-summary__hint">近 5 个交易日累计</div>
              </Card>
            </Col>

            <Col xs={12} sm={6} lg={4}>
              <Card
                className="national-team-summary__card"
                style={{
                  borderTop: (data?.summary?.change_20d_100m ?? 0) !== 0
                    ? `2px solid ${valueColor(data?.summary?.change_20d_100m, colors.up, colors.down, colors.border)}`
                    : undefined,
                }}
              >
                <Statistic
                  title="20 日份额变化"
                  value={formatSigned(data?.summary?.change_20d_100m)}
                  prefix={(data?.summary?.change_20d_100m ?? 0) > 0 ? <RiseOutlined /> : (data?.summary?.change_20d_100m ?? 0) < 0 ? <FallOutlined /> : undefined}
                  styles={{ content: { color: valueColor(data?.summary?.change_20d_100m, colors.up, colors.down, colors.textPrimary) } }}
                />
                <div className="national-team-summary__hint">近 20 个交易日累计</div>
              </Card>
            </Col>

            {/* 资金流向测算组 */}
            <Col xs={12} sm={8} lg={4}>
              <Card
                className="national-team-summary__card national-team-summary__card--flow"
                style={{
                  borderTop: (data?.summary?.estimated_net_flow_1d_100m ?? 0) !== 0
                    ? `2px solid ${valueColor(data?.summary?.estimated_net_flow_1d_100m, colors.up, colors.down, colors.border)}`
                    : undefined,
                }}
              >
                <Statistic
                  title="1 日估算净申购"
                  value={formatSigned(data?.summary?.estimated_net_flow_1d_100m, "亿元")}
                  prefix={(data?.summary?.estimated_net_flow_1d_100m ?? 0) > 0 ? <RiseOutlined /> : (data?.summary?.estimated_net_flow_1d_100m ?? 0) < 0 ? <FallOutlined /> : undefined}
                  styles={{ content: { color: valueColor(data?.summary?.estimated_net_flow_1d_100m, colors.up, colors.down, colors.textPrimary) } }}
                />
                <div className="national-team-summary__hint">较上一交易日资金</div>
              </Card>
            </Col>

            <Col xs={12} sm={8} lg={4}>
              <Card
                className="national-team-summary__card national-team-summary__card--flow"
                style={{
                  borderTop: (data?.summary?.estimated_net_flow_5d_100m ?? 0) !== 0
                    ? `2px solid ${valueColor(data?.summary?.estimated_net_flow_5d_100m, colors.up, colors.down, colors.border)}`
                    : undefined,
                }}
              >
                <Statistic
                  title="5 日估算净申购"
                  value={formatSigned(data?.summary?.estimated_net_flow_5d_100m, "亿元")}
                  prefix={(data?.summary?.estimated_net_flow_5d_100m ?? 0) > 0 ? <RiseOutlined /> : (data?.summary?.estimated_net_flow_5d_100m ?? 0) < 0 ? <FallOutlined /> : undefined}
                  styles={{ content: { color: valueColor(data?.summary?.estimated_net_flow_5d_100m, colors.up, colors.down, colors.textPrimary) } }}
                />
                <div className="national-team-summary__hint">近 5 个交易日累计资金</div>
              </Card>
            </Col>

            <Col xs={12} sm={8} lg={4}>
              <Card
                className="national-team-summary__card national-team-summary__card--flow"
                style={{
                  borderTop: (data?.summary?.estimated_net_flow_20d_100m ?? 0) !== 0
                    ? `2px solid ${valueColor(data?.summary?.estimated_net_flow_20d_100m, colors.up, colors.down, colors.border)}`
                    : undefined,
                }}
              >
                <Statistic
                  title="20 日估算净申购"
                  value={formatSigned(data?.summary?.estimated_net_flow_20d_100m, "亿元")}
                  prefix={(data?.summary?.estimated_net_flow_20d_100m ?? 0) > 0 ? <RiseOutlined /> : (data?.summary?.estimated_net_flow_20d_100m ?? 0) < 0 ? <FallOutlined /> : undefined}
                  styles={{ content: { color: valueColor(data?.summary?.estimated_net_flow_20d_100m, colors.up, colors.down, colors.textPrimary) } }}
                />
                <div className="national-team-summary__hint">近 20 个交易日累计资金</div>
              </Card>
            </Col>
          </Row>
        </div>

        {/* 全市场宽基每日净申赎走势堆叠图（含关键政策标尺） */}
        {data?.daily_flows && data.daily_flows.length > 0 && (
          <div className="national-team-daily-flow-section" style={{ marginBottom: 12 }}>
            <DailyFlowStackedChart dailyFlows={data.daily_flows} milestones={data?.milestones} />
          </div>
        )}

        {/* 关键政策底救市里程碑时间轴 */}
        {data?.milestones && data.milestones.length > 0 && (
          <div style={{ marginBottom: 12 }}>
            <MilestoneTimelineBar milestones={data.milestones} />
          </div>
        )}

        {/* 结构轮动卡片：横向轻量对比条 */}
        <Card
          className="national-team-rotation"
          title={
            <div className="national-team-rotation__header-left">
              <span className="national-team-rotation__title-text">{`结构轮动 · ${rotationWindow} 日份额变化`}</span>
              <span className="national-team-rotation__subtitle">跨宽基资金动向相对强弱</span>
            </div>
          }
          extra={
            <Segmented
              size="small"
              value={rotationWindow}
              options={[
                { label: "20 日", value: 20 },
                { label: "5 日", value: 5 },
                { label: "1 日", value: 1 },
              ]}
              onChange={(val) => setRotationWindowParam(String(val))}
              className="national-team-segmented"
            />
          }
        >
          <div className="national-team-rotation__list">
            {rotation.map((item, index) => {
              const currentVal = rotationWindow === 1
                ? item.latest_change_1d_100m
                : rotationWindow === 5
                ? item.change_5d_100m
                : item.change_20d_100m;
              const hasValue = currentVal != null;
              const barWidth = Math.max(6, Math.min(100, Math.round((Math.abs(currentVal ?? 0) / maxAbsRotation) * 100)));
              const isPositive = (currentVal ?? 0) >= 0;
              const rankClass = hasValue && index < 3 ? `national-team-rotation__rank--${index + 1}` : "";

              return (
                <div className="national-team-rotation__item" key={item.index_key}>
                  <span className={`national-team-rotation__rank ${rankClass}`}>{hasValue ? index + 1 : "-"}</span>
                  <div className="national-team-rotation__info">
                    <span className="national-team-rotation__name">{item.index_name}</span>
                    <span className="national-team-rotation__code">{item.index_code}</span>
                  </div>
                  <div className="national-team-rotation__bar" aria-hidden="true">
                    {hasValue && currentVal !== 0 && <span
                      style={{
                        width: `${barWidth}%`,
                        background: isPositive
                          ? `linear-gradient(90deg, ${colors.up}88, ${colors.up})`
                          : `linear-gradient(90deg, ${colors.down}88, ${colors.down})`,
                      }}
                    />}
                  </div>
                  <Text className="national-team-rotation__val" style={{ color: valueColor(currentVal, colors.up, colors.down, colors.textSecondary) }}>
                    {hasValue ? formatSigned(currentVal) : "数据不足"}
                  </Text>
                </div>
              );
            })}
          </div>
          <div className="national-team-rotation__footer">
            <Text type="secondary" className="national-team-rotation__note">
              排名反映纳入 ETF 的份额净变化，不代表真实持仓排名；数据不足时不参与排名。
            </Text>
          </div>
        </Card>

        {/* 核心指数主力成本中枢与托底点位分布 */}
        {data?.support_zones && data.support_zones.length > 0 && (
          <div style={{ marginBottom: 12 }}>
            <SupportZonesCard supportZones={data.support_zones} />
          </div>
        )}

        {/* 宽基图表矩阵：整洁紧凑的网格卡片 */}
        <div className="national-team-section-heading">
          <div className="national-team-section-heading__left">
            <Title level={2} className="national-team-section-heading__title">宽基份额与指数走势</Title>
            <Text type="secondary" className="national-team-section-heading__desc">
              左轴为纳入 ETF 合计份额，右轴为指数收盘点位
            </Text>
          </div>
          <div className="national-team-section-heading__controls">
            <Segmented
              aria-label="战术板块分类"
              value={category}
              options={CATEGORY_OPTIONS}
              onChange={(val) => handleCategoryChange(String(val))}
              className="national-team-segmented"
            />
            <Tag color="blue" className="national-team-section-heading__tag">双轴 · {days} 天</Tag>
          </div>
        </div>

        <div className="national-team-chart-grid">
          {filteredIndices.map((item) => <IndexDualAxisChart item={item} key={item.index_key} />)}
        </div>

        {/* ETF 监测明细表格 */}
        <div className="national-team-table-wrapper">
          <div className="national-team-section-heading national-team-section-heading--table">
            <div className="national-team-section-heading__left">
              <Title level={2} className="national-team-section-heading__title">ETF 监测明细</Title>
              <Text type="secondary" className="national-team-section-heading__desc">共 {filteredEtfs.length} 只；份额单位为亿份。</Text>
            </div>
            <div className="national-team-table-filters">
              <Space size={8} wrap>
                <Input
                  size="small"
                  placeholder="搜索代码 / 名称 / 基金公司"
                  prefix={<SearchOutlined style={{ color: "var(--c-text-muted)" }} />}
                  value={searchKeyword}
                  onChange={(e) => setSearchKeyword(e.target.value)}
                  allowClear
                  style={{ width: 190 }}
                />
                <Segmented
                  size="small"
                  value={selectedFilterIndex}
                  options={filterOptions}
                  onChange={(val) => setSelectedFilterIndex(String(val))}
                  className="national-team-segmented"
                />
                <Button
                  size="small"
                  icon={<DownloadOutlined />}
                  onClick={() => {
                    if (filteredEtfs.length === 0) {
                      message.warning("暂无数据可导出");
                      return;
                    }
                    downloadNationalTeamCsv(filteredEtfs, data?.as_of_date);
                    message.success(`已导出 ${filteredEtfs.length} 只 ETF 监测明细数据`);
                  }}
                  disabled={filteredEtfs.length === 0}
                >
                  导出 CSV
                </Button>
              </Space>
            </div>
          </div>
          <Card className="national-team-table-card" styles={{ body: { padding: 0 } }}>
            <Table
              rowKey="code"
              columns={columns}
              dataSource={filteredEtfs}
              pagination={false}
              scroll={{ x: isMobile ? 960 : 1160 }}
              size="small"
              className="national-team-table"
            />
          </Card>
        </div>

        {/* 底部口径与方法 */}
        <Card className="national-team-methodology" size="small">
          <Space align="start" size={12}>
            <SafetyCertificateOutlined className="national-team-methodology__icon" style={{ color: colors.primary }} />
            <div className="national-team-methodology__content">
              <div className="national-team-methodology__header">
                <Text strong>估算方法：</Text>
                <Text type="secondary">{data?.methodology || "ETF 当日份额变化 × ETF 当日收盘价，逐只计算后按宽基汇总。"}</Text>
              </div>
              <div className="national-team-methodology__footer">
                <Text type="secondary">
                  提示：ETF 份额变动为全市场申赎汇总结果，包含各类公募、私募、保险等机构及散户资金。
                </Text>
              </div>
            </div>
          </Space>
        </Card>
      </>
    )}
  </SectionDataState>
    </section>
  );
}
