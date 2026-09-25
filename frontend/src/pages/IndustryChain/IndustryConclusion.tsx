import IndustryClaimStatus from "./IndustryClaimStatus";
import {
  AimOutlined,
  BankOutlined,
  RiseOutlined,
  WarningOutlined,
} from "@ant-design/icons";
import { Tag, Typography } from "antd";
import type {
  IndustryChainEvidence,
  IndustryChainInsight,
  IndustryChainResult,
} from "../../types/stock";
import EvidenceLinkedText from "./EvidenceLinkedText";

const { Text } = Typography;

interface ConclusionItem {
  title: string;
  detail?: string;
  confidence?: IndustryChainInsight["confidence"];
}

function fallbackItems(items: string[]): ConclusionItem[] {
  return items.map((title) => ({ title }));
}

function coverageLabel(result: IndustryChainResult): {
  label: string;
  color: "success" | "warning" | "error";
} | null {
  const statuses = Object.values(result.coverage ?? {});
  if (statuses.length === 0) return null;
  if (statuses.every((status) => status === "complete")) {
    return { label: "证据完整", color: "success" };
  }
  if (statuses.some((status) => status === "complete" || status === "partial")) {
    return { label: "证据部分覆盖", color: "warning" };
  }
  return { label: "证据待补充", color: "error" };
}

function ConclusionList({
  title,
  icon,
  items,
  tone,
  evidenceCatalog,
}: {
  title: string;
  icon: React.ReactNode;
  items: ConclusionItem[];
  tone: "positive" | "negative";
  evidenceCatalog: IndustryChainEvidence[];
}) {
  if (items.length === 0) return null;
  return (
    <section className={`industry-conclusion__factor is-${tone}`}>
      <h3>{icon}{title}</h3>
      <ol>
        {items.slice(0, 3).map((item, index) => (
          <li key={`${item.title}-${index}`}>
            <div className="industry-conclusion__item-heading">
              <strong className="industry-conclusion__item-title">
                <EvidenceLinkedText text={item.title} evidenceCatalog={evidenceCatalog} />
              </strong>
              {item.confidence && (
                <span className="industry-conclusion__confidence">
                  {item.confidence === "high" ? "高" : item.confidence === "low" ? "低" : "中"}置信度
                </span>
              )}
            </div>
            {item.detail && <p><EvidenceLinkedText text={item.detail} evidenceCatalog={evidenceCatalog} /></p>}
          </li>
        ))}
      </ol>
    </section>
  );
}

export default function IndustryConclusion({ result }: { result: IndustryChainResult }) {
  const drivers = result.driver_insights?.length
    ? result.driver_insights
    : fallbackItems(result.drivers);
  const risks = result.risk_insights?.length
    ? result.risk_insights
    : fallbackItems(result.risks);
  const metrics = (result.market_metrics ?? []).slice(0, 3);
  const companies = result.key_stocks.slice(0, 4);
  const evidenceCatalog = result.evidence_catalog ?? [];
  const evidence = coverageLabel(result);
  const summaryCount = 1
    + metrics.length
    + Math.min(drivers.length, 3)
    + Math.min(risks.length, 3)
    + companies.length;

  return (
    <section
      id="industry-judgment"
      className="industry-conclusion pdf-section-block"
      aria-label="产业链结论摘要"
    >
      <header className="industry-conclusion__header">
        <div>
          <span className="industry-conclusion__eyebrow">01 · 产业研判</span>
          <h2>结论摘要</h2>
          <small className="industry-conclusion__count">{summaryCount} 项要点</small>
        </div>
        {evidence && <Tag color={evidence.color}>{evidence.label}</Tag>}
      </header>

      <div className="industry-conclusion__summary">
        <div className="industry-conclusion__label"><AimOutlined />核心判断</div>
        <p><EvidenceLinkedText text={result.summary || "当前证据不足，暂未形成可靠的产业判断。"} evidenceCatalog={evidenceCatalog} /></p>
        {result.positioning && (
          <div className="industry-conclusion__positioning">
            <Text type="secondary">产业定位</Text>
            <span><EvidenceLinkedText text={result.positioning} evidenceCatalog={evidenceCatalog} /></span>
          </div>
        )}
      </div>

      {metrics.length > 0 && (
        <div className="industry-conclusion__metrics" aria-label="关键指标">
          {metrics.map((metric) => (
            <div key={`${metric.label}-${metric.period || "latest"}`}>
              <span className="industry-conclusion__metric-label">{metric.label}</span>
              <strong className="industry-conclusion__metric-value">{metric.value}</strong>
              <IndustryClaimStatus claim={metric} />
              <small className="industry-conclusion__metric-meta">{[metric.period, metric.growth].filter(Boolean).join(" · ")}</small>
            </div>
          ))}
        </div>
      )}

      <div className="industry-conclusion__grid">
        <ConclusionList
          title="核心驱动"
          icon={<RiseOutlined />}
          items={drivers}
          tone="positive"
          evidenceCatalog={evidenceCatalog}
        />
        <ConclusionList
          title="主要风险"
          icon={<WarningOutlined />}
          items={risks}
          tone="negative"
          evidenceCatalog={evidenceCatalog}
        />
        {companies.length > 0 && (
          <section className="industry-conclusion__factor is-focus">
            <h3><BankOutlined />重点关注</h3>
            <ul className="industry-conclusion__companies">
              {companies.map((company, index) => (
                <li key={`${company.code || company.name}-${index}`}>
                  <div className="industry-conclusion__item-heading">
                    <strong className="industry-conclusion__item-title">
                      {company.name || company.company || company.code}
                    </strong>
                    {company.code && <Tag>{company.code}</Tag>}
                  </div>
                  {(company.role || company.description) && (
                    <p><EvidenceLinkedText text={company.role || company.description || ""} evidenceCatalog={evidenceCatalog} /></p>
                  )}
                </li>
              ))}
            </ul>
          </section>
        )}
      </div>
    </section>
  );
}
