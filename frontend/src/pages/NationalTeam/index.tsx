import { useMemo, useState } from "react";
import {
  Alert,
  Button,
  Card,
  Col,
  Empty,
  Row,
  Segmented,
  Space,
  Statistic,
  Table,
  Tag,
  Typography,
  Tooltip,
} from "antd";
import type { ColumnsType } from "antd/es/table";
import {
  BankOutlined,
  CalendarOutlined,
  DatabaseOutlined,
  FallOutlined,
  InfoCircleOutlined,
  ReloadOutlined,
  RiseOutlined,
  SafetyCertificateOutlined,
} from "@ant-design/icons";
import ReactECharts from "echarts-for-react/lib/core";
import echarts from "../../charts/echarts-setup";
import { useNationalTeamHoldings } from "../../api/queries";
import SectionDataState from "../../components/SectionDataState";
import { useColors } from "../../styles/ui";
import { buildStockProfileUrl } from "../../utils/stockLinks";
import type { NationalTeamEtfSeries, NationalTeamIndexSeries } from "../../types/stock";
import "./national-team.css";

const { Text, Title } = Typography;
const HISTORY_WINDOWS = [30, 60, 120, 240, 365] as const;
const INDEX_ORDER = ["沪深300", "上证50", "中证500", "中证1000", "科创50", "创业板"];

const INDEX_TAG_COLORS: Record<string, string> = {
  "沪深300": "blue",
  "上证50": "purple",
  "中证500": "cyan",
  "中证1000": "orange",
  "科创50": "volcano",
  "创业板": "geekblue",
};

function formatNumber(value: number | null | undefined, digits = 2) {
  if (value == null || !Number.isFinite(value)) return "-";
  return value.toLocaleString("zh-CN", {
    minimumFractionDigits: digits,
    maximumFractionDigits: digits,
  });
}

function formatShares(value: number | null | undefined) {
  return value == null ? "-" : `${formatNumber(value)} 亿份`;
}

function formatSigned(value: number | null | undefined, unit = "亿份") {
  if (value == null || !Number.isFinite(value)) return "-";
  return `${value > 0 ? "+" : ""}${formatNumber(value)} ${unit}`;
}

function valueColor(value: number | null | undefined, up: string, down: string, neutral: string) {
  if (value == null || value === 0) return neutral;
  return value > 0 ? up : down;
}

function IndexDualAxisChart({ item }: { item: NationalTeamIndexSeries }) {
  const colors = useColors();
  const points = useMemo(() => item.points ?? [], [item.points]);
  const showPointMarkers = points.length <= 1;
  const shareColor = colors.info || "#20c6e5";
  const indexColor = colors.warning || "#f59e0b";

  const option = useMemo(() => ({
    animationDuration: 350,
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
      textStyle: { color: colors.textPrimary, fontSize: 12 },
      extraCssText: "box-shadow: 0 8px 24px rgba(0, 0, 0, 0.22); border-radius: 8px; backdrop-filter: blur(8px);",
      formatter: (params: Array<{ axisValueLabel: string; marker: string; seriesName: string; value: number | null; dataIndex: number }>) => {
        if (!params.length) return "";
        const dataIdx = params[0].dataIndex;
        const pt = points[dataIdx];
        const rows = params.map((entry) => {
          const isShare = entry.seriesName === "ETF 合计份额";
          const unit = isShare ? "亿份" : "点";
          const formattedVal = formatNumber(entry.value, 2);
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
    grid: { left: 46, right: 46, top: 16, bottom: 22 },
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
        axisLabel: { color: colors.textSecondary, fontSize: 10, formatter: (val: number) => formatNumber(val, 1) },
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
          <div className="national-team-index-card__title-row">
            <Title level={3} className="national-team-index-card__title">{item.index_name}</Title>
            <Tag color={INDEX_TAG_COLORS[item.index_name] || "default"} className="national-team-index-card__tag">
              {item.index_code}
            </Tag>
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
    </Card>
  );
}

export default function NationalTeam() {
  const colors = useColors();
  const [days, setDays] = useState<number>(120);
  const [rotationWindow, setRotationWindow] = useState<20 | 5 | 1>(20);
  const [selectedFilterIndex, setSelectedFilterIndex] = useState<string>("ALL");
  const { data, isLoading, isFetching, error, refetch } = useNationalTeamHoldings(days);

  const indices = useMemo(() => [...(data?.indices ?? [])].sort(
    (a, b) => INDEX_ORDER.indexOf(a.index_name) - INDEX_ORDER.indexOf(b.index_name),
  ), [data?.indices]);

  const etfs = useMemo(() => data?.etfs ?? [], [data?.etfs]);
  const hasData = indices.length > 0 || etfs.length > 0;

  const rotation = useMemo(() => {
    const getVal = (item: NationalTeamIndexSeries) => {
      if (rotationWindow === 1) return item.latest_change_1d_100m;
      if (rotationWindow === 5) return item.change_5d_100m;
      return item.change_20d_100m;
    };
    return [...indices].sort(
      (a, b) => (getVal(b) ?? Number.NEGATIVE_INFINITY) - (getVal(a) ?? Number.NEGATIVE_INFINITY),
    );
  }, [indices, rotationWindow]);

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
    if (selectedFilterIndex === "ALL") return etfs;
    return etfs.filter((item) => item.index_name === selectedFilterIndex);
  }, [etfs, selectedFilterIndex]);

  const filterOptions = useMemo(() => [
    { label: `全部 (${etfs.length})`, value: "ALL" },
    ...INDEX_ORDER.filter((name) => etfs.some((e) => e.index_name === name)).map((name) => ({
      label: `${name} (${etfs.filter((e) => e.index_name === name).length})`,
      value: name,
    })),
  ], [etfs]);

  const columns: ColumnsType<NationalTeamEtfSeries> = [
    {
      title: "宽基",
      dataIndex: "index_name",
      key: "index_name",
      width: 95,
      fixed: "left",
      render: (name: string) => (
        <Tag color={INDEX_TAG_COLORS[name] || "default"} className="national-team-index-tag">
          {name}
        </Tag>
      ),
    },
    {
      title: "ETF",
      key: "etf",
      width: 210,
      render: (_, item) => (
        <div className="national-team-etf-name">
          <div className="national-team-etf-code-row">
            <a
              href={buildStockProfileUrl(item.code)}
              className="national-team-code national-team-code-link"
              title={`查看 ${item.name}（${item.code}）行情`}
            >
              {item.code}
            </a>
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
      title: "基金公司",
      dataIndex: "fund_manager",
      key: "fund_manager",
      width: 110,
      render: (val: string) => <Text className="national-team-subtle-text">{val || "-"}</Text>,
    },
    {
      title: "最新日期",
      dataIndex: "latest_date",
      key: "latest_date",
      width: 100,
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
    {
      title: "最新份额",
      dataIndex: "latest_shares_100m",
      key: "latest_shares_100m",
      width: 125,
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
        width: 115,
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
  ];

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
                覆盖 12 只核心宽基 ETF
              </span>
            </div>
          </div>
        </div>

        <div className="national-team-hero__controls">
          <Segmented
            aria-label="历史区间"
            value={days}
            options={HISTORY_WINDOWS.map((value) => ({ label: `${value} 天`, value }))}
            onChange={(value) => setDays(Number(value))}
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
            title={data.refreshing ? "数据不完整 · 后台更新中" : "数据不完整"}
            description={[
              data.stale ? `份额截至 ${data.as_of_date || "未知"}，预期交易日 ${data.expected_date || "待确认"}。` : "",
              data.calendar_degraded ? "交易日历暂不可用，新鲜度与区间完整性待确认。" : "",
              data.missing_share_etfs?.length ? `份额缺失或区间不完整：${data.missing_share_etfs.join("、")}。` : "",
              data.missing_price_etfs?.length ? `ETF 行情缺失：${data.missing_price_etfs.join("、")}。` : "",
              data.missing_indices?.length ? `指数行情缺失：${data.missing_indices.map((key) => data.indices?.find((item) => item.index_key === key)?.index_name || key).join("、")}。` : "",
              data.observations?.length ? "无业务日期的当前份额仅作未确认观察，不计入历史与资金估算。" : "",
              "汇总仅覆盖截至日有份额数据的 ETF；变化按相同标的、相同交易日比较，无法计算时显示“-”，不代表零变化。请谨慎解读。",
            ].join("")}
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
                <div className="national-team-summary__hint">覆盖 {data?.covered_etf_count ?? 0}/{data?.total_etf_count ?? 12} 只宽基 ETF · 截至 {data?.as_of_date || "-"}</div>
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
            <Col xs={12} sm={6} lg={4}>
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
                <div className="national-team-summary__hint">收盘价估算资金</div>
              </Card>
            </Col>

            <Col xs={12} sm={6} lg={4}>
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
                <div className="national-team-summary__hint">20 日累计估算资金</div>
              </Card>
            </Col>
          </Row>
        </div>

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
              onChange={(val) => setRotationWindow(Number(val) as 20 | 5 | 1)}
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

        {/* 宽基图表矩阵：整洁紧凑的网格卡片 */}
        <div className="national-team-section-heading">
          <div className="national-team-section-heading__left">
            <Title level={2} className="national-team-section-heading__title">宽基份额与指数走势</Title>
            <Text type="secondary" className="national-team-section-heading__desc">
              左轴为纳入 ETF 合计份额，右轴为指数收盘点位
            </Text>
          </div>
          <Tag color="blue" className="national-team-section-heading__tag">双轴 · {days} 天</Tag>
        </div>

        <div className="national-team-chart-grid">
          {indices.map((item) => <IndexDualAxisChart item={item} key={item.index_key} />)}
        </div>

        {/* ETF 监测明细表格 */}
        <div className="national-team-table-wrapper">
          <div className="national-team-section-heading national-team-section-heading--table">
            <div className="national-team-section-heading__left">
              <Title level={2} className="national-team-section-heading__title">ETF 监测明细</Title>
              <Text type="secondary" className="national-team-section-heading__desc">共 {etfs.length} 只；份额单位为亿份。</Text>
            </div>
            <div className="national-team-table-filters">
              <Segmented
                size="small"
                value={selectedFilterIndex}
                options={filterOptions}
                onChange={(val) => setSelectedFilterIndex(String(val))}
                className="national-team-segmented"
              />
            </div>
          </div>
          <Card className="national-team-table-card" styles={{ body: { padding: 0 } }}>
            <Table
              rowKey="code"
              columns={columns}
              dataSource={filteredEtfs}
              pagination={false}
              scroll={{ x: 960 }}
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
      </SectionDataState>
    </section>
  );
}
