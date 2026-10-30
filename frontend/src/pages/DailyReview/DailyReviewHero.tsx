import { CompassOutlined, RiseOutlined } from "@ant-design/icons";
import { Card, Progress, Tag, Typography } from "antd";
import { useColors } from "../../styles/ui";
import { formatSignedPct, stageTone, type DailyReviewPayload, type ReviewHeadline } from "./reviewView";
import "./daily-review-hero.css";

const { Paragraph, Text } = Typography;

interface DailyReviewHeroProps {
  review: DailyReviewPayload;
  headline: ReviewHeadline;
  moodSummary: string;
  checkAccuracy: number | null;
}

/**
 * 复盘首屏结论卡。
 *
 * 打开页面先给「一句话结论 + 三个关键数字 + 情绪阶段 + 昨日自检命中率」，
 * 让用户不必滚完整页才知道今天该关注什么。
 */
export default function DailyReviewHero({ review, headline, moodSummary, checkAccuracy }: DailyReviewHeroProps) {
  const c = useColors();
  const stageColor = {
    up: c.up,
    down: c.down,
    warning: c.warning,
    neutral: c.textMuted,
  }[stageTone(headline.stage)];

  const indexTone = (headline.indexChangePct ?? 0) >= 0 ? c.up : c.down;

  return (
    <Card
      className="daily-review-hero"
      style={{ borderLeft: `4px solid ${c.primary}`, background: `linear-gradient(135deg, color-mix(in srgb, ${c.primary} 6%, ${c.cardBg}), ${c.cardBg})` }}
    >
      <div className="daily-review-hero__top">
        <div className="daily-review-hero__headline">
          <div className="daily-review-hero__title-row">
            <h2 className="daily-review-hero__title">{review.title}</h2>
            <div className="daily-review-hero__badges">
              <Tag color={headline.quality === "degraded" ? "warning" : "success"}>
                质量：{headline.quality === "degraded" ? "降级" : "完整"}
              </Tag>
              <Tag color={headline.generation === "fallback" ? "warning" : "processing"}>
                报告：{headline.generation === "fallback" ? "确定性兜底" : "AI 生成"}
              </Tag>
            </div>
          </div>
          <Paragraph className="daily-review-hero__summary">{review.market_summary}</Paragraph>
          <div className="daily-review-hero__mood">
            <Text strong style={{ color: c.primary }}>
              <CompassOutlined style={{ marginRight: 6 }} />
              市场情绪结论：
            </Text>
            <Text style={{ marginLeft: 6 }}>{moodSummary}</Text>
          </div>
        </div>

        {checkAccuracy !== null ? (
          <div className="daily-review-hero__check" aria-label="昨日复盘自检命中率">
            <Progress
              type="circle"
              size={72}
              percent={Math.round(checkAccuracy * 100)}
              strokeColor={c.primary}
              trailColor="var(--c-border)"
              format={(percent) => <span className="daily-review-hero__check-value">{percent}%</span>}
            />
            <div className="daily-review-hero__check-caption">
              昨日自检
              <div>
                <Text type="secondary">
                  命中 {headline.checkHit}/{headline.checkTotal}
                </Text>
              </div>
            </div>
          </div>
        ) : null}
      </div>

      <dl className="daily-review-hero__metrics">
        <div className="daily-review-hero__metric">
          <dt>涨停家数</dt>
          <dd className="financial-num">{headline.limitUpCount ?? "—"}</dd>
        </div>
        <div className="daily-review-hero__metric">
          <dt>炸板率</dt>
          <dd className="financial-num">
            {headline.breakRate === null ? "—" : `${headline.breakRate.toFixed(1)}%`}
          </dd>
        </div>
        <div className="daily-review-hero__metric">
          <dt>{headline.indexName || "指数涨跌"}</dt>
          <dd className="financial-num" style={{ color: indexTone }}>
            <RiseOutlined style={{ marginRight: 4 }} />
            {formatSignedPct(headline.indexChangePct)}
          </dd>
        </div>
        <div className="daily-review-hero__metric">
          <dt>情绪阶段</dt>
          <dd style={{ color: stageColor }}>{headline.stage || "未定位"}</dd>
        </div>
      </dl>

      <Text type="secondary" className="daily-review-hero__timestamp">
        复盘日期 {review.date} · 生成时间 {review.generated_at || "-"}
      </Text>
    </Card>
  );
}
