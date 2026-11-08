import { useMemo } from "react";
import { Card, Col, Row, Tag, Tooltip, Typography } from "antd";
import { InfoCircleOutlined } from "@ant-design/icons";
import { useColors } from "../../../styles/ui";
import { formatSignedPercent } from "../../../utils/format";
import { buildSparklinePath } from "../../../utils/sparkline";
import type {
  NationalTeamSupportBacktest,
  NationalTeamSupportHistoryPoint,
  NationalTeamSupportScore,
} from "../../../types/stock";

const { Text } = Typography;

const STATUS_CLASSES = ["strong", "active", "moderate"] as const;

export default function SupportScoreRadarCard({
  supportScore,
  history,
  backtest,
}: {
  supportScore?: NationalTeamSupportScore;
  history?: NationalTeamSupportHistoryPoint[];
  backtest?: NationalTeamSupportBacktest;
}) {
  const colors = useColors();
  const sparkline = useMemo(
    () => buildSparklinePath((history ?? []).slice(-30).map((point) => point.score), 168, 28),
    [history],
  );
  const backtestHorizons = (backtest?.horizons ?? []).filter((item) => item.samples > 0);
  if (!supportScore) return null;

  const score = supportScore.score;
  const confidence = supportScore.confidence ?? 0;
  const confidencePct = Math.round(confidence * 100);
  const confidenceColor = confidence >= 0.8 ? "blue" : confidence >= 0.5 ? "gold" : "default";
  const confidenceHint =
    confidence >= 0.8
      ? "ETF 覆盖率与数据新鲜度良好。"
      : confidence >= 0.5
      ? "部分 ETF 份额或行情缺失，结论仅供参考。"
      : "样本覆盖不足或数据陈旧，请勿据此单独决策。";
  const status = (STATUS_CLASSES as readonly string[]).includes(supportScore.status)
    ? supportScore.status
    : "neutral";
  const statusTagColor =
    status === "strong" ? "blue" : status === "active" ? "orange" : status === "moderate" ? "cyan" : "default";

  return (
    <Card
      className="national-team-support-radar-card"
      size="small"
      data-testid="national-team-support-radar"
      styles={{ body: { padding: "12px 16px" } }}
    >
      <Row gutter={[16, 12]} align="middle">
        <Col xs={24} md={8} lg={7}>
          <div className="national-team-support-radar__head">
            <div className={`national-team-support-radar__score is-${status}`}>
              <span className="national-team-support-radar__score-value">{Math.round(score)}</span>
              <span className="national-team-support-radar__score-label">强度指数</span>
            </div>
            <div>
              <div className="national-team-support-radar__title">
                <span className="national-team-support-radar__title-text">国家队托底雷达</span>
                <Tag color={statusTagColor} className="national-team-support-radar__label-tag">
                  {supportScore.label}
                </Tag>
                <Tooltip title={confidenceHint}>
                  <Tag
                    color={confidenceColor}
                    className="national-team-support-radar__confidence-tag"
                    data-testid="national-team-support-confidence"
                  >
                    置信度 {confidencePct}%
                  </Tag>
                </Tooltip>
              </div>
              <Text type="secondary" className="national-team-support-radar__desc">
                {supportScore.description || "综合测算资金流入、板块覆盖度与抗跌偏离。"}
                {supportScore.percentile_60d != null
                  ? ` · 近60日分位 ${Math.round(supportScore.percentile_60d)}%`
                  : ""}
              </Text>
            </div>
          </div>
        </Col>

        <Col xs={24} md={16} lg={17}>
          <Row gutter={[12, 8]}>
            <Col xs={24} sm={8}>
              <div className="national-team-factor-item">
                <div className="national-team-factor-item__head">
                  <span className="national-team-factor-item__label">资金托底因子</span>
                  <span className="national-team-factor-item__value">{supportScore.net_flow_factor} / 40</span>
                </div>
                <div className="national-team-factor-item__track">
                  <div
                    className="national-team-factor-item__fill is-primary"
                    style={{ width: `${Math.min(100, (supportScore.net_flow_factor / 40) * 100)}%` }}
                  />
                </div>
              </div>
            </Col>
            <Col xs={24} sm={8}>
              <div className="national-team-factor-item">
                <div className="national-team-factor-item__head">
                  <span className="national-team-factor-item__label">板块扩散因子</span>
                  <span className="national-team-factor-item__value">{supportScore.breadth_factor} / 30</span>
                </div>
                <div className="national-team-factor-item__track">
                  <div
                    className="national-team-factor-item__fill is-info"
                    style={{ width: `${Math.min(100, (supportScore.breadth_factor / 30) * 100)}%` }}
                  />
                </div>
              </div>
            </Col>
            <Col xs={24} sm={8}>
              <div className="national-team-factor-item">
                <div className="national-team-factor-item__head">
                  <span className="national-team-factor-item__label">逆势抗跌因子</span>
                  <span className="national-team-factor-item__value">{supportScore.divergence_factor} / 30</span>
                </div>
                <div className="national-team-factor-item__track">
                  <div
                    className="national-team-factor-item__fill is-warning"
                    style={{ width: `${Math.min(100, (supportScore.divergence_factor / 30) * 100)}%` }}
                  />
                </div>
              </div>
            </Col>
          </Row>
        </Col>
      </Row>
      {sparkline && (
        <div className="national-team-support-radar__sparkline" data-testid="national-team-score-sparkline">
          <span className="national-team-support-radar__sparkline-label">托底评分走势</span>
          <svg
            width={sparkline.width}
            height={sparkline.height}
            viewBox={`0 0 ${sparkline.width} ${sparkline.height}`}
            role="img"
            aria-label={`近 ${sparkline.count} 个交易日托底评分走势`}
            className="national-team-support-radar__sparkline-svg"
          >
            <path
              d={sparkline.path}
              fill="none"
              stroke={sparkline.delta >= 0 ? colors.primary : colors.textSecondary}
              strokeWidth={1.5}
              strokeLinejoin="round"
              strokeLinecap="round"
            />
          </svg>
          <span className="national-team-support-radar__sparkline-delta">
            {sparkline.count} 日 {sparkline.delta >= 0 ? "+" : ""}
            {sparkline.delta.toFixed(1)}
          </span>
        </div>
      )}
      {backtestHorizons.length > 0 ? (
        <div className="national-team-support-radar__backtest" data-testid="national-team-backtest">
          <span className="national-team-support-radar__sparkline-label">信号后表现</span>
          {backtestHorizons.map((item) => (
            <span key={item.days} className="national-team-support-radar__backtest-item">
              {item.days} 日 {formatSignedPercent(item.avg_return_pct)} · 胜率 {item.win_rate_pct ?? "-"}%
              <span className="national-team-support-radar__backtest-samples">（{item.samples}）</span>
            </span>
          ))}
          <Tooltip
            title={
              [
                backtest?.note,
                backtest &&
                (backtest.excluded_low_confidence ?? 0) + (backtest.excluded_low_coverage ?? 0) > 0
                  ? `已剔除 ${backtest.excluded_low_confidence ?? 0} 个低置信度、${backtest.excluded_low_coverage ?? 0} 个低覆盖样本`
                  : "",
                backtest?.first_sample_date && backtest?.last_sample_date
                  ? `样本区间 ${backtest.first_sample_date} ~ ${backtest.last_sample_date}`
                  : "",
              ]
                .filter(Boolean)
                .join("；") || "基于已落库评分与沪深300 收盘，仅统计有未来行情的信号。"
            }
          >
            <InfoCircleOutlined className="national-team-support-radar__info-icon" />
          </Tooltip>
          {backtest &&
          (backtest.excluded_low_confidence ?? 0) + (backtest.excluded_low_coverage ?? 0) > 0 ? (
            <span className="national-team-support-radar__backtest-note">
              已剔除 {(backtest.excluded_low_confidence ?? 0) + (backtest.excluded_low_coverage ?? 0)} 个低质量样本
            </span>
          ) : null}
        </div>
      ) : null}
    </Card>
  );
}
