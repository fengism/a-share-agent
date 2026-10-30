import { Card, Typography } from "antd";
import { useColors } from "../../../styles/ui";
import { formatSignedPct, stageTone, type DailyReviewPayload } from "../reviewView";
import "./daily-review-sections.css";

const { Paragraph, Text } = Typography;

type TrendPayload = NonNullable<DailyReviewPayload["cycle_trend"]>;

interface CycleTrendTimelineProps {
  trend: TrendPayload;
}

/**
 * 情绪周期历史趋势（横向时间轴）。
 *
 * 原先用 Space wrap 平铺小方块，看不出"升级/降级"的方向；改成横向时间轴后
 * 阶段色带、涨停家数、指数涨跌能沿时间顺序读出来，窄屏可横向滑动。
 */
export default function CycleTrendTimeline({ trend }: CycleTrendTimelineProps) {
  const c = useColors();
  const points = (trend.points ?? []).slice(-10);
  const toneColor = {
    up: c.up,
    down: c.down,
    warning: c.warning,
    neutral: c.textMuted,
  };

  if (points.length === 0) return null;

  return (
    <Card size="small" className="daily-review-trend-card">
      {trend.note ? <Paragraph type="secondary" className="daily-review-trend-card__note">{trend.note}</Paragraph> : null}

      <div className="daily-review-trend" role="list" aria-label="情绪周期时间轴">
        {points.map((point) => {
          const color = toneColor[stageTone(point.stage)];
          return (
            <div key={point.date} className="daily-review-trend__node" role="listitem" data-tone={stageTone(point.stage)}>
              <div className="daily-review-trend__stage" style={{ color, borderColor: color }}>
                {point.stage || "未定位"}
              </div>
              {point.stage_transition ? (
                <div className="daily-review-trend__transition" data-transition={point.stage_transition}>
                  {point.stage_transition === "升级" ? "▲" : point.stage_transition === "降级" ? "▼" : "—"}
                  {point.stage_transition}
                </div>
              ) : (
                <div className="daily-review-trend__transition">—</div>
              )}
              <div className="daily-review-trend__metric financial-num">
                涨停 {point.limit_up_count ?? "-"}
              </div>
              <div className="daily-review-trend__metric financial-num">
                炸板 {point.break_rate == null ? "-" : `${(point.break_rate * 100).toFixed(1)}%`}
              </div>
              <div className="daily-review-trend__metric financial-num" style={{ color: (point.index_change_pct ?? 0) >= 0 ? c.up : c.down }}>
                指数 {formatSignedPct(point.index_change_pct)}
              </div>
              {point.next_index_change_pct != null ? (
                <div className="daily-review-trend__metric financial-num" style={{ color: (point.next_index_change_pct ?? 0) >= 0 ? c.up : c.down }}>
                  次日 {formatSignedPct(point.next_index_change_pct)}
                </div>
              ) : null}
              <div className="daily-review-trend__date">{point.date.slice(5)}</div>
            </div>
          );
        })}
      </div>

      {trend.stage_stats?.length ? (
        <div className="daily-review-trend__stats">
          {trend.stage_stats.map((stat) => (
            <Text key={stat.stage} type="secondary">
              {stat.stage}：出现 {stat.occurrences} 次
              {stat.next_day_up_ratio != null ? `，次日指数上涨 ${(stat.next_day_up_ratio * 100).toFixed(0)}%` : ""}
              {stat.avg_next_day_index_change_pct != null ? `，平均次日 ${formatSignedPct(stat.avg_next_day_index_change_pct)}` : ""}
            </Text>
          ))}
        </div>
      ) : null}
    </Card>
  );
}
