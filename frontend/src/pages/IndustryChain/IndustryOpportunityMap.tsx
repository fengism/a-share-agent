import { Progress, Tag, Typography } from "antd";
import { FileSearchOutlined } from "@ant-design/icons";
import type { IndustryChainOpportunity } from "../../types/stock";

const { Text } = Typography;
const bounded = (value?: number) => typeof value === "number" && Number.isFinite(value)
  ? Math.max(0, Math.min(100, value)) : 0;

export default function IndustryOpportunityMap({ opportunities }: { opportunities?: IndustryChainOpportunity[] }) {
  if (!opportunities?.length) return null;
  return (
    <section className="industry-opportunity-map" aria-labelledby="industry-opportunity-map-heading">
      <header>
        <div><FileSearchOutlined /><strong id="industry-opportunity-map-heading">公司研究资料</strong></div>
        <Text type="secondary">按资料完整度排列，不代表投资价值或收益预期</Text>
      </header>
      <ol>
        {opportunities.map((item, index) => {
          const current = item.scoring_version === 2 && item.score_kind === "research_completeness";
          return (
            <li key={`${item.code || item.name}-${index}`}>
              <div className="industry-opportunity-map__content">
                <div className="industry-opportunity-map__title">
                  <strong className="industry-opportunity-map__name">{item.name}</strong>{item.code && <Tag>{item.code}</Tag>}
                  {item.role && <Text className="industry-opportunity-map__role" type="secondary">{item.role}</Text>}
                  <span className="industry-opportunity-map__completeness">{current ? `资料完整度 ${bounded(item.completeness_score)}%` : "旧版评分已停用"}</span>
                </div>
                {current && <Progress percent={bounded(item.completeness_score)} showInfo={false} size="small" />}
                <Text type="secondary">盈利、估值、景气：未评估</Text>
                {current && <p>角色、描述、指标、有效证据各占 25%；完整度不等于事实准确性。</p>}
                {item.rationale && <p>{item.rationale}</p>}
              </div>
            </li>
          );
        })}
      </ol>
    </section>
  );
}
