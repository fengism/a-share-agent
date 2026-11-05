import { useMemo } from "react";
import { CompassOutlined, RiseOutlined } from "@ant-design/icons";
import { Card, Progress, Tag, Tooltip, Typography } from "antd";
import { useColors } from "../../styles/ui";
import { formatSignedPct, stageTone, type DailyReviewPayload, type ReviewHeadline } from "./reviewView";
import { analyzeSentiment } from "./sentimentAnalyzer";
import "./daily-review-hero.css";

const { Paragraph, Text } = Typography;

interface DailyReviewHeroProps {
  review: DailyReviewPayload;
  headline: ReviewHeadline;
  moodSummary: string;
  checkAccuracy: number | null;
}

/**
 * 复盘首屏结论卡与 5-Factor 量化情绪罗盘。
 *
 * 融合「一句话结论 + 量化情绪温度计 + 战术操作指引 + 5因子微量表 + 核心盘面指标 + 昨日自检命中率」，
 * 帮助用户在第一屏秒级洞悉大盘所处位置与最佳应对策略。
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

  const sentiment = useMemo(() => {
    return analyzeSentiment(review, headline);
  }, [review, headline]);

  return (
    <Card
      className="daily-review-hero"
      style={{
        borderLeft: `4px solid ${sentiment.color || c.primary}`,
        background: `linear-gradient(135deg, color-mix(in srgb, ${sentiment.color || c.primary} 7%, ${c.cardBg}), ${c.cardBg})`,
      }}
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

          {/* 量化情绪罗盘 & 今日战术指引栏 */}
          <div
            className="daily-review-hero__sentiment-box"
            style={{
              borderColor: `color-mix(in srgb, ${sentiment.color} 30%, var(--c-border))`,
              background: `color-mix(in srgb, ${sentiment.color} 8%, var(--c-card-bg))`,
            }}
          >
            <div className="daily-review-hero__sentiment-header">
              <div className="daily-review-hero__sentiment-title">
                <span className="daily-review-hero__sentiment-icon">{sentiment.zoneIcon}</span>
                <span className="daily-review-hero__sentiment-temp financial-num" style={{ color: sentiment.color }}>
                  {sentiment.temperature}°C
                </span>
                <Tag
                  variant="filled"
                  style={{
                    background: `color-mix(in srgb, ${sentiment.color} 20%, transparent)`,
                    color: sentiment.color,
                    fontWeight: 600,
                    fontSize: 12,
                    margin: 0,
                  }}
                >
                  {sentiment.zoneLabel}
                </Tag>
              </div>

              <div className="daily-review-hero__tactics">
                <Text strong style={{ color: "var(--c-text-primary)" }}>战术策略：</Text>
                <Text style={{ color: sentiment.color, fontWeight: 500 }}>{sentiment.tactics}</Text>
              </div>
            </div>

            {/* 5-Factor 因子雷达水平条 */}
            <div className="daily-review-hero__factors">
              <Tooltip title="两市多空上涨家数占比">
                <div className="daily-review-hero__factor-item">
                  <span className="factor-label">上涨广度</span>
                  <div className="factor-progress-bg">
                    <div className="factor-progress-bar" style={{ width: `${sentiment.factors.breadth}%`, backgroundColor: sentiment.color }} />
                  </div>
                  <span className="factor-val financial-num">{sentiment.factors.breadth}</span>
                </div>
              </Tooltip>

              <Tooltip title="指数动量与涨跌拉动力">
                <div className="daily-review-hero__factor-item">
                  <span className="factor-label">动量积聚</span>
                  <div className="factor-progress-bg">
                    <div className="factor-progress-bar" style={{ width: `${sentiment.factors.momentum}%`, backgroundColor: sentiment.color }} />
                  </div>
                  <span className="factor-val financial-num">{sentiment.factors.momentum}</span>
                </div>
              </Tooltip>

              <Tooltip title="两市总成交金额与放缩量级别">
                <div className="daily-review-hero__factor-item">
                  <span className="factor-label">资金量能</span>
                  <div className="factor-progress-bg">
                    <div className="factor-progress-bar" style={{ width: `${sentiment.factors.turnover}%`, backgroundColor: sentiment.color }} />
                  </div>
                  <span className="factor-val financial-num">{sentiment.factors.turnover}</span>
                </div>
              </Tooltip>

              <Tooltip title="涨停封板率与炸板风险稳定性">
                <div className="daily-review-hero__factor-item">
                  <span className="factor-label">结构稳定</span>
                  <div className="factor-progress-bg">
                    <div className="factor-progress-bar" style={{ width: `${sentiment.factors.stability}%`, backgroundColor: sentiment.color }} />
                  </div>
                  <span className="factor-val financial-num">{sentiment.factors.stability}</span>
                </div>
              </Tooltip>

              <Tooltip title="情绪周期所处阶段">
                <div className="daily-review-hero__factor-item">
                  <span className="factor-label">周期定位</span>
                  <div className="factor-progress-bg">
                    <div className="factor-progress-bar" style={{ width: `${sentiment.factors.cycle}%`, backgroundColor: sentiment.color }} />
                  </div>
                  <span className="factor-val financial-num">{sentiment.factors.cycle}</span>
                </div>
              </Tooltip>
            </div>
          </div>

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
              railColor="var(--c-border)"
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
