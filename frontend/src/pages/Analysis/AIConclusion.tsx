import type { CSSProperties } from "react";
import { Card, Progress, Typography } from "antd";
import RatingBadge from "../../components/RatingBadge";
import SignalBadge from "../../components/SignalBadge";
import { renderWithCitations } from "../../features/investment-research/CitationText";
import type { AnalysisResult } from "../../types/stock";
import { useColors, useStyles, useTokens } from "../../theme/hooks";
import "./analysis-conclusion.css";

const { Text } = Typography;

interface Props {
  result: AnalysisResult;
  embedded?: boolean;
}

export default function AIConclusion({ result, embedded = false }: Props) {
  const c = useColors();
  const t = useTokens();
  const { cardStyle } = useStyles();
  const {
    fundamental,
    valuation_view,
    fair_value_range,
    overall_rating,
    overall_summary,
    estimated_price_range,
    signal,
    confidence,
    key_factors,
    risk_warnings,
    current_price,
  } = result;

  const rf = result.research_framework;
  const baseFairRange = rf?.valuation?.scenarios?.base?.fair_value_range;
  const actionBuyRange = rf?.actions?.buy_or_add_range;

  // 优先提取有效 (> 0) 的 12 个月估值目标区间，其次尝试回退至公允价值区间或基准情景
  const validEstRange = estimated_price_range && estimated_price_range[0] > 0 && estimated_price_range[1] > 0
    ? estimated_price_range
    : (fair_value_range && fair_value_range[0] > 0 && fair_value_range[1] > 0
      ? fair_value_range
      : (baseFairRange && baseFairRange[0] > 0 && baseFairRange[1] > 0
        ? baseFairRange
        : (actionBuyRange && actionBuyRange[0] > 0 && actionBuyRange[1] > 0 ? actionBuyRange : null)));

  const priceLow = validEstRange ? validEstRange[0] : null;
  const priceHigh = validEstRange ? validEstRange[1] : null;
  const priceRangeText = priceLow != null && priceHigh != null
    ? `¥${priceLow.toFixed(2)} – ¥${priceHigh.toFixed(2)}`
    : "证据不足 · 待核验";

  const priceChange = current_price && current_price > 0 && priceHigh && priceHigh > 0
    ? ((priceHigh - current_price) / current_price * 100).toFixed(1)
    : null;
  const isBuy = signal === "buy" || signal === "strong_buy";
  const isSell = signal === "sell" || signal === "strong_sell";
  const accent = isBuy ? c.up : isSell ? c.down : c.primary;
  const accentSoft = isBuy ? c.upBg : isSell ? c.downBg : `${c.primary}14`;
  const scoreColor = (score: number) => score >= 8 ? c.up : score >= 6 ? c.primary : score >= 4 ? c.warning : c.down;
  const dimensionScores = [
    { label: "基本面", score: fundamental.score, summary: fundamental.summary },
  ];
  const valuationText = valuation_view || "暂无明确结论";
  const valuationRange = fair_value_range?.[0] != null && fair_value_range[0] > 0
    ? `¥${fair_value_range[0].toFixed(2)} – ¥${fair_value_range[1].toFixed(2)}`
    : "暂无公允区间";

  const conclusionStyle = {
    ...(embedded ? {} : cardStyle),
    marginBottom: embedded ? 0 : t.space[4],
    "--analysis-accent": accent,
    "--analysis-accent-soft": accentSoft,
  } as CSSProperties;

  const content = (
    <>
      <section className="analysis-conclusion__hero pdf-avoid-break" aria-label="综合研判">
        <div className="analysis-conclusion__decision-row">
          <div className="analysis-conclusion__decision-copy">
            <span className="analysis-conclusion__eyebrow">核心判断</span>
            <p className="analysis-conclusion__summary">{renderWithCitations(overall_summary)}</p>
          </div>
          <div className="analysis-conclusion__signal-cluster">
            <RatingBadge score={overall_rating} size={56} />
            <div className="analysis-conclusion__signal-meta">
              <SignalBadge signal={signal} />
              <span>模型置信度 {Math.round(confidence * 100)}%</span>
              <Progress
                percent={Math.round(confidence * 100)}
                size="small"
                showInfo={false}
                strokeColor={accent}
                aria-label="模型置信度"
              />
            </div>
          </div>
        </div>
      </section>

      <div className="analysis-conclusion__content">
        <div className="analysis-conclusion__metrics pdf-avoid-break">
          <div className="analysis-conclusion__metric">
            <span>12个月估值区间</span>
            <strong>{priceRangeText}</strong>
          </div>
          <div className="analysis-conclusion__metric">
            <span>当前价与预期空间</span>
            <strong>
              {current_price && current_price > 0 ? `¥${current_price.toFixed(2)}` : "--"}
              {priceChange ? <em className={Number(priceChange) >= 0 ? "is-positive" : "is-negative"}>{Number(priceChange) >= 0 ? "+" : ""}{priceChange}%</em> : null}
            </strong>
          </div>
          <div className="analysis-conclusion__metric analysis-conclusion__metric--valuation">
            <span>估值结论</span>
            <strong className="analysis-conclusion__valuation-text">{valuationText}</strong>
            <small>{valuationRange}</small>
          </div>
        </div>

        <div className="analysis-conclusion__decision-grid pdf-avoid-break">
          <section className="analysis-conclusion__score-panel" aria-label="分项评分">
            <h3>决策因子</h3>
            <div className="analysis-conclusion__score-list">
              {dimensionScores.map((item) => (
                <div className="analysis-conclusion__score-row" key={item.label}>
                  <div className="analysis-conclusion__score-heading">
                    <span>{item.label}</span>
                    <strong>{item.score.toFixed(1)}</strong>
                  </div>
                  <Progress percent={item.score * 10} showInfo={false} strokeColor={scoreColor(item.score)} size="small" aria-label={`${item.label}评分`} />
                  <p>{item.summary}</p>
                </div>
              ))}
            </div>
          </section>

          <div className="analysis-conclusion__factor-grid">
            <section className="analysis-conclusion__factor-card is-positive">
              <h3>核心驱动</h3>
              {key_factors.length ? (
                <ul className="analysis-factor-list">
                  {key_factors.map((item, index) => <li key={`${item}-${index}`}><span>+</span>{item}</li>)}
                </ul>
              ) : <Text type="secondary">暂无</Text>}
            </section>
            <section className="analysis-conclusion__factor-card is-negative">
              <h3>主要风险</h3>
              {risk_warnings.length ? (
                <ul className="analysis-factor-list">
                  {risk_warnings.map((item, index) => <li key={`${item}-${index}`}><span>!</span>{item}</li>)}
                </ul>
              ) : <Text type="secondary">暂无</Text>}
            </section>
          </div>
        </div>
      </div>
    </>
  );

  if (embedded) {
    return (
      <section
        className="analysis-conclusion analysis-conclusion--embedded"
        data-pdf-capture
        aria-labelledby="analysis-conclusion-title"
        style={conclusionStyle}
      >
        <header className="analysis-conclusion__section-header">
          <h2 id="analysis-conclusion-title">综合研判</h2>
        </header>
        {content}
      </section>
    );
  }

  return (
    <Card
      size="small"
      className="analysis-conclusion pdf-avoid-break"
      title={<span className="analysis-conclusion__title">AI 综合研判</span>}
      style={conclusionStyle}
      styles={{ body: { padding: 0 } }}
    >
      {content}
    </Card>
  );
}
