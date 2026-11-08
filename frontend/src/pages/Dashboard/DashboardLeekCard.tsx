import { ArrowRightOutlined, FireOutlined } from "@ant-design/icons";
import { Card, Tag } from "antd";
import { useLeekIndexOverview } from "../../api/queryHooks/sentiment";
import PreloadLink from "../../components/PreloadLink";
import "./dashboard-leek-card.css";

const STATUS_STYLE = {
  extreme: { color: "var(--c-danger, #f5222d)", border: "2px solid #f5222d", tag: "red", label: "🔥 极度接盘" },
  fever: { color: "var(--c-warning, #fa8c16)", border: "2px solid #fa8c16", tag: "orange", label: "⚠️ 散户过热" },
  normal: { color: "var(--c-primary, #1677ff)", border: "2px solid #1677ff", tag: "blue", label: "⚖️ 筹码均衡" },
  safe: { color: "var(--c-success, #52c41a)", border: "2px solid #52c41a", tag: "green", label: "💎 筹码出清" },
} as const;

export default function DashboardLeekCard() {
  const { data, isLoading } = useLeekIndexOverview();

  if (isLoading && !data) {
    return <Card size="small" loading className="dashboard-leek-card" data-testid="dashboard-leek-card" />;
  }
  if (!data) return null;

  const median = Math.round(data.summary.median_score);
  let statusKey: "extreme" | "fever" | "normal" | "safe" = "normal";
  if (median >= 75) statusKey = "extreme";
  else if (median >= 60) statusKey = "fever";
  else if (median <= 35) statusKey = "safe";

  const st = STATUS_STYLE[statusKey];
  const topFever = data.industries.slice(0, 2);

  return (
    <Card
      size="small"
      className="dashboard-leek-card"
      data-testid="dashboard-leek-card"
      styles={{ body: { padding: "10px 14px" } }}
    >
      <div className="dashboard-leek-card__inner">
        <div
          aria-hidden
          className="dashboard-leek-card__dial"
          style={{ border: st.border, color: st.color }}
        >
          <span className="dashboard-leek-card__dial-score">{median}</span>
          <span className="dashboard-leek-card__dial-label">散户温度</span>
        </div>

        <div className="dashboard-leek-card__content">
          <div className="dashboard-leek-card__topline">
            <span className="dashboard-leek-card__title">
              <FireOutlined style={{ color: "#fa541c", marginRight: 4 }} />
              行业韭菜指数
            </span>
            <Tag color={st.tag} style={{ marginInlineEnd: 0 }}>{st.label}</Tag>
            <span style={{ fontSize: 11, color: "var(--c-text-muted)" }}>
              极度接盘 {data.summary.extreme_count} 个 / 出清 {data.summary.safe_count} 个
            </span>
          </div>

          <div className="dashboard-leek-card__hot-hint">
            <span>散户聚集前列:</span>
            {topFever.map((ind) => (
              <Tag key={ind.industry_name} className="dashboard-leek-card__tag">
                {ind.industry_name} ({ind.leek_score.toFixed(0)}分)
              </Tag>
            ))}
          </div>
        </div>

        <PreloadLink
          to="/leek-index"
          className="dashboard-leek-card__link"
          aria-label="查看行业韭菜指数看板"
        >
          查看雷达 <ArrowRightOutlined />
        </PreloadLink>
      </div>
    </Card>
  );
}
