import { BarChartOutlined } from "@ant-design/icons";
import { Card, Skeleton } from "antd";
import type { StockBasicInfo } from "../../types/stock";
import { useStyles } from "../../styles/ui";
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
}

/** 指标定义。标签是静态的，先于数据渲染出来，用户能立刻看到卡片结构。 */
const METRICS: Array<{
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

export default function StockMetrics({ info }: StockMetricsProps) {
  const { cardStyle } = useStyles();

  return (
    <Card
      className="stock-section-card stock-metrics-card"
      title={<StockSectionTitle icon={<BarChartOutlined />} title="关键指标" description="规模、估值与交易活跃度" />}
      style={cardStyle}
      styles={{ body: { padding: 0 } }}
    >
      <dl className="stock-metrics-grid" aria-busy={info ? undefined : true}>
        {METRICS.map((metric) => (
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