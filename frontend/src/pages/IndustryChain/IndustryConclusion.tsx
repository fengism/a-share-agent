import {
  AimOutlined,
  BankOutlined,
  RiseOutlined,
  WarningOutlined,
} from "@ant-design/icons";
import { Tag, Typography } from "antd";
import type {
  IndustryChainInsight,
  IndustryChainResult,
} from "../../types/stock";

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
}: {
  title: string;
  icon: React.ReactNode;
  items: ConclusionItem[];
  tone: "positive" | "negative";
}) {
  if (items.length === 0) return null;
  return (
    <section className={`industry-conclusion__factor is-${tone}`}>
      <h3>{icon}{title}</h3>
      <ol>
        {items.slice(0, 3).map((item, index) => (
          <li key={`${item.title}-${index}`}>
            <div>
              <strong>{item.title}</strong>
              {item.confidence && (
                <span>
                  {item.confidence === "high" ? "高" : item.confidence === "low" ? "低" : "中"}置信度
                </span>
              )}
            </div>
            {item.detail && <p>{item.detail}</p>}
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
        <p>{result.summary || "当前证据不足，暂未形成可靠的产业判断。"}</p>
        {result.positioning && (
          <div className="industry-conclusion__positioning">
            <Text type="secondary">产业定位</Text>
            <span>{result.positioning}</span>
          </div>
        )}
      </div>

      {metrics.length > 0 && (
        <div className="industry-conclusion__metrics" aria-label="关键指标">
          {metrics.map((metric) => (
            <div key={`${metric.label}-${metric.period || "latest"}`}>
              <span>{metric.label}</span>
              <strong>{metric.value}</strong>
              <small>{[metric.period, metric.growth].filter(Boolean).join(" · ")}</small>
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
        />
        <ConclusionList
          title="主要风险"
          icon={<WarningOutlined />}
          items={risks}
          tone="negative"
        />
        {companies.length > 0 && (
          <section className="industry-conclusion__factor is-focus">
            <h3><BankOutlined />重点关注</h3>
            <ul className="industry-conclusion__companies">
              {companies.map((company, index) => (
                <li key={`${company.code || company.name}-${index}`}>
                  <div>
                    <strong>{company.name || company.company || company.code}</strong>
                    {company.code && <Tag>{company.code}</Tag>}
                  </div>
                  {(company.role || company.description) && (
                    <p>{company.role || company.description}</p>
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
