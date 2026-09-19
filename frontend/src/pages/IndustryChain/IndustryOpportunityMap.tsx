import { Progress, Tag, Typography } from "antd";
import { TrophyOutlined } from "@ant-design/icons";
import type { IndustryChainOpportunity } from "../../types/stock";

const { Text } = Typography;

const SCORE_ITEMS: Array<{ key: keyof IndustryChainOpportunity; label: string }> = [
  { key: "prosperity_score", label: "景气" },
  { key: "earnings_score", label: "盈利" },
  { key: "valuation_score", label: "估值" },
  { key: "catalyst_score", label: "催化" },
  { key: "evidence_score", label: "证据" },
  { key: "risk_score", label: "风险" },
];

function scoreValue(opportunity: IndustryChainOpportunity, key: keyof IndustryChainOpportunity) {
  const value = opportunity[key];
  return typeof value === "number" ? Math.max(0, Math.min(100, value)) : 0;
}

export default function IndustryOpportunityMap({
  opportunities,
}: {
  opportunities?: IndustryChainOpportunity[];
}) {
  if (!opportunities?.length) return null;

  return (
    <section className="industry-opportunity-map" aria-labelledby="industry-opportunity-map-heading">
      <header>
        <div>
          <TrophyOutlined />
          <strong id="industry-opportunity-map-heading">投资研究地图</strong>
        </div>
        <Text type="secondary">研究优先级，不构成买卖建议</Text>
      </header>
      <ol>
        {opportunities.map((opportunity, index) => (
          <li key={`${opportunity.code || opportunity.name}-${index}`}>
            <div className="industry-opportunity-map__rank">{index + 1}</div>
            <div className="industry-opportunity-map__content">
              <div className="industry-opportunity-map__title">
                <strong>{opportunity.name}</strong>
                {opportunity.code && <Tag>{opportunity.code}</Tag>}
                {opportunity.role && <Text type="secondary">{opportunity.role}</Text>}
                <span>{opportunity.total_score} 分</span>
              </div>
              <Progress
                percent={scoreValue(opportunity, "total_score")}
                showInfo={false}
                size="small"
                strokeColor="var(--c-primary)"
              />
              <div className="industry-opportunity-map__scores">
                {SCORE_ITEMS.map(({ key, label }) => (
                  <span key={key}>{label} {scoreValue(opportunity, key)}</span>
                ))}
              </div>
              {opportunity.rationale && (
                <p>{opportunity.rationale}</p>
              )}
            </div>
          </li>
        ))}
      </ol>
    </section>
  );
}
