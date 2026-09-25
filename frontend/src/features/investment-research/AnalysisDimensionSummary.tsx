import type { ReactNode } from "react";
import RatingBadge from "../../components/RatingBadge";
import "./analysis-dimension-summary.css";

interface Props {
  label: string;
  score?: number | null;
  children: ReactNode;
}

export default function AnalysisDimensionSummary({ label, score, children }: Props) {
  return (
    <section className="analysis-dimension-summary" aria-label={`${label}概览`}>
      <section className="analysis-dimension-summary__score" aria-label={`${label}评分`}>
        {score == null ? (
          <div className="analysis-dimension-summary__score-empty" aria-label="暂无评分">-</div>
        ) : (
          <RatingBadge score={score} size={56} />
        )}
        <strong>{label}</strong>
      </section>
      <section className="analysis-dimension-summary__content" aria-label={`${label}详情`}>
        {children}
      </section>
    </section>
  );
}
