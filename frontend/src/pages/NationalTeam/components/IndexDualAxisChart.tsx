import { useMemo, useState } from "react";
import { Button, Card, Empty, Modal, Space, Tag, Typography } from "antd";
import { FullscreenOutlined } from "@ant-design/icons";
import ReactECharts from "echarts-for-react/lib/core";
import echarts from "../../../charts/echarts-setup";
import { useNationalTeamIndexSeriesItem } from "../../../api/queries";
import { useColors } from "../../../styles/ui";
import { APP_FONT_FAMILY } from "../../../theme/typography";
import { formatNumberWithSeparators } from "../../../utils/format";
import type { NationalTeamIndexSeries } from "../../../types/stock";
import { INDEX_TAG_COLORS } from "../constants";
import { formatShares, formatSigned, valueColor } from "../utils/format";
import { escapeHtml } from "../utils/html";
import LazyChart from "./LazyChart";

const { Text, Title } = Typography;

export default function IndexDualAxisChart({
  item: itemProp,
  days,
}: {
  item: NationalTeamIndexSeries;
  days: number;
}) {
  const colors = useColors();
  const [expanded, setExpanded] = useState(false);
  const seriesResult = useNationalTeamIndexSeriesItem(itemProp.index_key, days);
  const series = seriesResult?.data;
  const isLoading = seriesResult?.isLoading ?? false;
  const isError = seriesResult?.isError ?? false;
  const refetch = seriesResult?.refetch ?? (() => {});
  // 首屏响应只有标量，点位在图表进入视口后才单独拉取；拉到之前先用标量占位。
  const item = series ?? itemProp;
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
            <span style="display:flex;align-items:center;gap:6px;font-size:12px">${entry.marker}${escapeHtml(entry.seriesName)}</span>
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

        // 覆盖率不全的点位与完整点位在图上长得一样，必须在 tooltip 里明确区分，
        // 否则用户会把「只覆盖 3/4 只 ETF 的合计」当成整条指数的完整数据。
        if (pt && pt.total_etf_count > 0 && pt.covered_etf_count < pt.total_etf_count) {
          flowNote += `<div style="display:flex;justify-content:space-between;align-items:center;gap:20px;margin-top:3px;font-size:11px;color:#d48806">
            <span>成员覆盖不全</span>
            <span style="font-family:var(--c-font-mono);font-weight:600">${pt.covered_etf_count}/${pt.total_etf_count} 只</span>
          </div>`;
        }

        return `<div style="font-weight:600;margin-bottom:4px;font-size:12px;color:${colors.textPrimary}">${escapeHtml(params[0].axisValueLabel)}</div>${rows}${flowNote}`;
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

  if (isLoading && !series) {
    return (
      <Card
        className="national-team-index-card"
        size="small"
        loading
        data-testid="national-team-index-loading"
      />
    );
  }

  if (isError && !series) {
    return (
      <Card className="national-team-index-card" size="small" styles={{ body: { padding: 16 } }}>
        <Space direction="vertical" size={6}>
          <Text type="secondary">指数序列加载失败（{itemProp.index_name}）</Text>
          <Button size="small" onClick={() => void refetch()}>重试</Button>
        </Space>
      </Card>
    );
  }

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
        <LazyChart height={215}>
          <ReactECharts
            echarts={echarts}
            option={option}
            className="national-team-index-card__chart"
            style={{ width: "100%", height: 215 }}
            notMerge
          />
        </LazyChart>
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
