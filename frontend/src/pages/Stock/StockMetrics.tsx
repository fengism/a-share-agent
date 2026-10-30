import { BarChartOutlined } from "@ant-design/icons";
import { Card, Skeleton } from "antd";
import type { HKStockQuote } from "../../api/queryHooks/hk";
import type { StockBasicInfo } from "../../types/stock";
import { useColors, useStyles } from "../../styles/ui";
import { formatNumberWithSeparators } from "../../utils/format";
import StockSectionTitle from "./StockSectionTitle";

interface StockMetricsProps {
  /**
   * 允许缺省：概览网格是 `minmax(520px,1.18fr) minmax(360px,0.82fr)` 双列，
   * 若数据未到时整张卡片不渲染，兄弟卡片会先占住宽列、数据到达后再被挤到窄列，
   * 文本重排导致整页下移（实测 CLS 0.28）。
   *
   * 缺省时渲染**同样式**的指标网格（标签 + 数值位骨架），既占住列位、
   * 又让几何尺寸与加载后完全一致，不产生二次位移。
   */
  info?: StockBasicInfo;
  market?: "cn" | "hk";
  hkQuote?: HKStockQuote | null;
}

/** A 股指标定义。标签是静态的，先于数据渲染出来，用户能立刻看到卡片结构。 */
const CN_METRICS: Array<{
  label: string;
  featured?: boolean;
  format: (info: StockBasicInfo) => string;
}> = [
  { label: "总市值", featured: true, format: (i) => formatLargeNumber(i.market_cap, "currency") },
  { label: "流通市值", featured: true, format: (i) => formatLargeNumber(i.float_market_cap, "currency") },
  { label: "总股本", format: (i) => formatLargeNumber(i.total_shares, "shares") },
  { label: "流通股本", format: (i) => formatLargeNumber(i.circulating_shares, "shares") },
  { label: "市盈率 TTM", format: (i) => formatRatio(i.pe_ttm) },
  { label: "静态市盈率", format: (i) => formatRatio(i.pe_static) },
  { label: "市净率", format: (i) => formatRatio(i.pb) },
  { label: "换手率", format: (i) => formatRatio(i.turnover_pct, "%") },
  { label: "上市日期", format: (i) => i.listing_date || "-" },
];

function formatAmount(value: number | null | undefined) {
  if (value == null) return "-";
  if (Math.abs(value) >= 1e8) return `${(value / 1e8).toFixed(2)}亿`;
  if (Math.abs(value) >= 1e4) return `${(value / 1e4).toFixed(1)}万`;
  return formatNumberWithSeparators(value, 0);
}

function formatLargeNumber(value: number | null, unit: "currency" | "shares") {
  if (value == null || !Number.isFinite(value)) return "-";
  if (Math.abs(value) >= 1e12) return `${(value / 1e12).toFixed(2)}万亿`;
  if (Math.abs(value) >= 1e8) return `${(value / 1e8).toFixed(2)}亿`;
  if (Math.abs(value) >= 1e4) return `${(value / 1e4).toFixed(2)}万`;
  return unit === "currency" ? value.toFixed(2) : value.toLocaleString("zh-CN");
}

function formatRatio(value: number | null, suffix = "") {
  return value == null || !Number.isFinite(value) ? "-" : `${value.toFixed(2)}${suffix}`;
}

export default function StockMetrics({ info, market = "cn", hkQuote }: StockMetricsProps) {
  const colors = useColors();
  const { cardStyle } = useStyles();
  const isHK = market === "hk";

  const getPriceColor = (price: number | null | undefined, preClose: number | null | undefined) => {
    if (price == null || preClose == null) return undefined;
    if (price > preClose) return colors.up;
    if (price < preClose) return colors.down;
    return undefined;
  };

  if (isHK) {
    const amplitude =
      hkQuote?.high != null && hkQuote?.low != null && hkQuote?.pre_close != null && hkQuote.pre_close > 0
        ? ((hkQuote.high - hkQuote.low) / hkQuote.pre_close) * 100
        : null;

    return (
      <Card
        className="stock-section-card stock-metrics-card"
        title={<StockSectionTitle icon={<BarChartOutlined />} title="关键行情指标" description="港股主板盘口与成交明细" />}
        style={cardStyle}
        styles={{ body: { padding: 0 } }}
      >
        <dl className="stock-metrics-grid" aria-busy={hkQuote ? undefined : true}>
          <div className="stock-metric stock-metric--featured">
            <dt>今开盘</dt>
            <dd style={{ color: getPriceColor(hkQuote?.open, hkQuote?.pre_close) }}>
              {hkQuote ? formatNumberWithSeparators(hkQuote.open) : <Skeleton.Button active block size="small" />}
            </dd>
          </div>
          <div className="stock-metric stock-metric--featured">
            <dt>昨收盘</dt>
            <dd>{hkQuote ? formatNumberWithSeparators(hkQuote.pre_close) : <Skeleton.Button active block size="small" />}</dd>
          </div>
          <div className="stock-metric">
            <dt>最高价</dt>
            <dd style={{ color: getPriceColor(hkQuote?.high, hkQuote?.pre_close) }}>
              {hkQuote ? formatNumberWithSeparators(hkQuote.high) : <Skeleton.Button active block size="small" />}
            </dd>
          </div>
          <div className="stock-metric">
            <dt>最低价</dt>
            <dd style={{ color: getPriceColor(hkQuote?.low, hkQuote?.pre_close) }}>
              {hkQuote ? formatNumberWithSeparators(hkQuote.low) : <Skeleton.Button active block size="small" />}
            </dd>
          </div>
          <div className="stock-metric">
            <dt>振幅</dt>
            <dd>{hkQuote ? (amplitude != null ? `${amplitude.toFixed(2)}%` : "-") : <Skeleton.Button active block size="small" />}</dd>
          </div>
          <div className="stock-metric">
            <dt>市盈率 (TTM)</dt>
            <dd>{hkQuote ? (hkQuote.pe_ttm != null ? hkQuote.pe_ttm.toFixed(2) : "-") : <Skeleton.Button active block size="small" />}</dd>
          </div>
          <div className="stock-metric">
            <dt>市净率</dt>
            <dd>{hkQuote ? (hkQuote.pb != null ? hkQuote.pb.toFixed(2) : "-") : <Skeleton.Button active block size="small" />}</dd>
          </div>
          <div className="stock-metric">
            <dt>总市值</dt>
            <dd>{hkQuote ? (hkQuote.market_cap != null ? `${formatAmount(hkQuote.market_cap)} 港元` : "-") : <Skeleton.Button active block size="small" />}</dd>
          </div>
          <div className="stock-metric">
            <dt>流通市值</dt>
            <dd>{hkQuote ? (hkQuote.float_market_cap != null ? `${formatAmount(hkQuote.float_market_cap)} 港元` : "-") : <Skeleton.Button active block size="small" />}</dd>
          </div>
          <div className="stock-metric">
            <dt>成交额</dt>
            <dd>{hkQuote ? `${formatAmount(hkQuote.amount)} 港元` : <Skeleton.Button active block size="small" />}</dd>
          </div>
          <div className="stock-metric">
            <dt>成交量</dt>
            <dd>{hkQuote ? `${formatAmount(hkQuote.volume)} 股` : <Skeleton.Button active block size="small" />}</dd>
          </div>
          <div className="stock-metric">
            <dt>买一价 / 卖一价</dt>
            <dd>
              {hkQuote ? (
                <>
                  <span style={{ color: getPriceColor(hkQuote.bid, hkQuote.pre_close) }}>
                    {formatNumberWithSeparators(hkQuote.bid)}
                  </span>
                  {" / "}
                  <span style={{ color: getPriceColor(hkQuote.ask, hkQuote.pre_close) }}>
                    {formatNumberWithSeparators(hkQuote.ask)}
                  </span>
                </>
              ) : (
                <Skeleton.Button active block size="small" />
              )}
            </dd>
          </div>
          <div className="stock-metric">
            <dt>数据更新时间</dt>
            <dd style={{ fontSize: 12 }}>{hkQuote ? (hkQuote.updated_at || "实时交易中") : <Skeleton.Button active block size="small" />}</dd>
          </div>
        </dl>
      </Card>
    );
  }

  return (
    <Card
      className="stock-section-card stock-metrics-card"
      title={<StockSectionTitle icon={<BarChartOutlined />} title="关键指标" description="规模、估值与交易活跃度" />}
      style={cardStyle}
      styles={{ body: { padding: 0 } }}
    >
      <dl className="stock-metrics-grid" aria-busy={info ? undefined : true}>
        {CN_METRICS.map((metric) => (
          <div className={`stock-metric${metric.featured ? " stock-metric--featured" : ""}`} key={metric.label}>
            <dt>{metric.label}</dt>
            {info ? (
              <dd>{metric.format(info)}</dd>
            ) : (
              <dd className="stock-metric__placeholder" aria-hidden="true">
                <Skeleton.Button active block size="small" />
              </dd>
            )}
          </div>
        ))}
      </dl>
    </Card>
  );
}