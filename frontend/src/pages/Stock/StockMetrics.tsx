import { BarChartOutlined } from "@ant-design/icons";
import { Card } from "antd";
import type { StockBasicInfo } from "../../types/stock";
import { useStyles } from "../../styles/ui";
import StockSectionTitle from "./StockSectionTitle";

interface StockMetricsProps {
  info: StockBasicInfo;
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

export default function StockMetrics({ info }: StockMetricsProps) {
  const { cardStyle } = useStyles();
  const metrics = [
    { label: "总市值", value: formatLargeNumber(info.market_cap, "currency"), featured: true },
    { label: "流通市值", value: formatLargeNumber(info.float_market_cap, "currency"), featured: true },
    { label: "总股本", value: formatLargeNumber(info.total_shares, "shares") },
    { label: "流通股本", value: formatLargeNumber(info.circulating_shares, "shares") },
    { label: "市盈率 TTM", value: formatRatio(info.pe_ttm) },
    { label: "静态市盈率", value: formatRatio(info.pe_static) },
    { label: "市净率", value: formatRatio(info.pb) },
    { label: "换手率", value: formatRatio(info.turnover_pct, "%") },
    { label: "上市日期", value: info.listing_date || "-" },
  ];

  return (
    <Card
      className="stock-section-card stock-metrics-card"
      title={<StockSectionTitle icon={<BarChartOutlined />} title="关键指标" description="规模、估值与交易活跃度" />}
      style={cardStyle}
      styles={{ body: { padding: 0 } }}
    >
      <dl className="stock-metrics-grid">
        {metrics.map((metric) => (
          <div className={`stock-metric${metric.featured ? " stock-metric--featured" : ""}`} key={metric.label}>
            <dt>{metric.label}</dt>
            <dd>{metric.value}</dd>
          </div>
        ))}
      </dl>
    </Card>
  );
}
