import { useMemo, useState } from "react";
import { Alert, Card, Radio, Tag } from "antd";
import ReactECharts from "echarts-for-react/lib/core";
import dayjs from "dayjs";
import { useSgeGoldHistory } from "../../api/queries";
import SectionDataState from "../../components/SectionDataState";
import { useColors } from "../../styles/ui";
import echarts from "../../charts/echarts-setup";

const SGE_SYMBOLS = [
  ["Au99.99", "黄金 Au99.99"],
  ["Au99.95", "黄金 Au99.95"],
  ["Au100g", "黄金 Au100g"],
  ["Pt99.95", "铂金 Pt99.95"],
  ["Ag(T+D)", "白银 Ag(T+D)"],
  ["Au(T+D)", "黄金 Au(T+D)"],
  ["mAu(T+D)", "迷你黄金 mAu(T+D)"],
  ["Au(T+N1)", "黄金 Au(T+N1)"],
  ["Au(T+N2)", "黄金 Au(T+N2)"],
  ["Ag99.99", "白银 Ag99.99"],
  ["iAu99.99", "国际板黄金 iAu99.99"],
  ["Au99.5", "黄金 Au99.5"],
  ["iAu100g", "国际板黄金 iAu100g"],
  ["iAu99.5", "国际板黄金 iAu99.5"],
  ["PGC30g", "熊猫金币 PGC30g"],
  ["NYAuTN06", "沪纽金 NYAuTN06"],
  ["NYAuTN12", "沪纽金 NYAuTN12"],
] as const;

const RANGE_OPTIONS = [
  { label: "1月", value: "1m", months: 1 },
  { label: "3月", value: "3m", months: 3 },
  { label: "6月", value: "6m", months: 6 },
  { label: "1年", value: "1y", months: 12 },
  { label: "全部", value: "all", months: null },
] as const;

type RangeValue = (typeof RANGE_OPTIONS)[number]["value"];

function formatPrice(value: number | null | undefined) {
  return value == null ? "-" : value.toFixed(2);
}

function formatSigned(value: number | null | undefined, suffix = "") {
  if (value == null) return "-";
  return `${value > 0 ? "+" : ""}${value.toFixed(2)}${suffix}`;
}

export default function SgeGoldTab() {
  const c = useColors();
  const [symbol, setSymbol] = useState("Au99.99");
  const [range, setRange] = useState<RangeValue>("1y");
  const { data, isLoading, error, refetch } = useSgeGoldHistory(symbol);

  const filteredHistory = useMemo(() => {
    const history = data?.history ?? [];
    const rangeOption = RANGE_OPTIONS.find((item) => item.value === range);
    if (!rangeOption?.months || history.length === 0) return history;
    const latestDate = dayjs(history[history.length - 1]?.date);
    const startDate = latestDate.subtract(rangeOption.months, "month");
    return history.filter((item) => !dayjs(item.date).isBefore(startDate, "day"));
  }, [data?.history, range]);

  const chartOption = useMemo(() => ({
    animation: false,
    backgroundColor: "transparent",
    tooltip: {
      trigger: "axis",
      axisPointer: { type: "cross" },
      formatter: (params: Array<{ axisValue: string; data: number[] }>) => {
        const point = params[0];
        if (!point) return "";
        const [open, close, low, high] = point.data;
        return [
          point.axisValue,
          `开盘：${formatPrice(open)}`,
          `收盘：${formatPrice(close)}`,
          `最低：${formatPrice(low)}`,
          `最高：${formatPrice(high)}`,
        ].join("<br/>");
      },
    },
    grid: { left: 18, right: 18, top: 24, bottom: 42, containLabel: true },
    xAxis: {
      type: "category",
      data: filteredHistory.map((item) => item.date),
      boundaryGap: true,
      axisLine: { lineStyle: { color: c.border } },
      axisLabel: { color: c.textSecondary, hideOverlap: true },
      axisTick: { show: false },
    },
    yAxis: {
      type: "value",
      scale: true,
      axisLabel: { color: c.textSecondary },
      splitLine: { lineStyle: { color: c.border, type: "dashed" } },
    },
    dataZoom: [
      { type: "inside", start: 0, end: 100 },
      {
        type: "slider",
        height: 18,
        bottom: 4,
        borderColor: "transparent",
        backgroundColor: c.nestedBg,
        fillerColor: `${c.primary}20`,
        handleStyle: { color: c.primary },
        textStyle: { color: c.textSecondary },
      },
    ],
    series: [{
      name: data?.name ?? symbol,
      type: "candlestick",
      data: filteredHistory.map((item) => [item.open, item.close, item.low, item.high]),
      itemStyle: {
        color: c.up,
        color0: c.down,
        borderColor: c.up,
        borderColor0: c.down,
      },
    }],
  }), [c, data?.name, filteredHistory, symbol]);

  const latest = data?.latest;
  const changeTone = (latest?.change_pct ?? 0) > 0
    ? "sge-gold-summary__value--up"
    : (latest?.change_pct ?? 0) < 0
      ? "sge-gold-summary__value--down"
      : "";

  return (
    <section className="sge-gold">
      <div className="sge-gold__toolbar">
        <div>
          <div className="sge-gold__eyebrow">SHANGHAI GOLD EXCHANGE</div>
          <h2 className="sge-gold__title">上金所贵金属走势</h2>
          <p className="sge-gold__description">跟踪上海黄金交易所主要黄金、白银与铂金合约的日线 OHLC 行情。</p>
        </div>
        <label className="sge-gold__selector">
          <span>交易品种</span>
          <select
            aria-label="黄金品种"
            value={symbol}
            onChange={(event) => setSymbol(event.target.value)}
          >
            {SGE_SYMBOLS.map(([value, label]) => (
              <option key={value} value={value}>{value} · {label.split(" ")[0]}</option>
            ))}
          </select>
        </label>
      </div>

      <SectionDataState
        isLoading={isLoading && !data}
        error={data ? undefined : error}
        onRetry={() => refetch()}
        isEmpty={!data || !latest || data.history.length === 0}
        emptyText="暂无上金所历史行情"
        errorTitle="上金所行情加载失败"
        minHeight={420}
      >
        {data && latest ? (
          <>
            {data.is_stale ? (
              <Alert
                className="sge-gold__stale-alert"
                type="warning"
                showIcon
                message="实时数据暂时不可用，当前展示最近一次历史快照"
              />
            ) : null}

            <div className="sge-gold-summary">
              <Card className="sge-gold-summary__primary" variant="borderless">
                <div className="sge-gold-summary__name-row">
                  <div>
                    <strong>{data.name}</strong>
                    <span>{data.symbol}</span>
                  </div>
                  <Tag color="gold">{data.unit}</Tag>
                </div>
                <div className="sge-gold-summary__price financial-num">{formatPrice(latest.close)}</div>
                <div className={`sge-gold-summary__change financial-num ${changeTone}`}>
                  <span>{formatSigned(latest.change)}</span>
                  <span>{formatSigned(latest.change_pct, "%")}</span>
                </div>
              </Card>

              <div className="sge-gold-summary__metrics">
                <div className="sge-gold-summary__metric">
                  <span>开盘</span>
                  <strong className="financial-num">{formatPrice(latest.open)}</strong>
                </div>
                <div className="sge-gold-summary__metric">
                  <span>当日低 / 高</span>
                  <strong className="financial-num">{formatPrice(latest.low)} / {formatPrice(latest.high)}</strong>
                </div>
                <div className="sge-gold-summary__metric">
                  <span>数据日期</span>
                  <strong>{latest.date}</strong>
                </div>
                <div className="sge-gold-summary__metric">
                  <span>数据来源</span>
                  <strong>{data.source}</strong>
                </div>
              </div>
            </div>

            <Card className="sge-gold-chart" variant="borderless">
              <div className="sge-gold-chart__header">
                <div>
                  <h3>日线价格走势</h3>
                  <span>开盘 / 收盘 / 最低 / 最高</span>
                </div>
                <Radio.Group
                  optionType="button"
                  buttonStyle="solid"
                  size="small"
                  options={RANGE_OPTIONS.map(({ label, value }) => ({ label, value }))}
                  value={range}
                  onChange={(event) => setRange(event.target.value as RangeValue)}
                  aria-label="时间范围"
                />
              </div>
              <ReactECharts
                echarts={echarts}
                className="sge-gold-chart__canvas"
                option={chartOption}
                notMerge
                lazyUpdate
              />
              <div className="sge-gold-chart__footer">
                <span>共 {filteredHistory.length} 个交易日</span>
                <span>更新于 {dayjs(data.updated_at).format("YYYY-MM-DD HH:mm")}</span>
              </div>
            </Card>
          </>
        ) : null}
      </SectionDataState>
    </section>
  );
}
