import type { ReactNode } from "react";
import { Col, Row, Table, Tag, Typography } from "antd";
import type { TableProps } from "antd";
import { useMediaQuery } from "../../hooks/useMediaQuery";
import { useColors } from "../../styles/ui";
import type {
  IndustryChainCompetitionGroup,
  IndustryChainConflict,
  IndustryChainCoverage,
  IndustryChainEvidence,
  IndustryChainEvidenceStats,
  IndustryChainInsight,
  IndustryChainMetric,
  IndustryChainNode,
  IndustryChainResult,
  IndustryChainSource,
} from "../../types/stock";

const { Paragraph, Text } = Typography;

function ResearchBlock({
  title,
  children,
  className = "",
}: {
  title: string;
  children: ReactNode;
  className?: string;
}) {
  return (
    <section className={`industry-research-block ${className}`.trim()}>
      <h3 className="industry-research-block__title">{title}</h3>
      <div className="industry-research-block__body">{children}</div>
    </section>
  );
}

function AuditDisclosure({
  title,
  summary,
  children,
}: {
  title: string;
  summary?: string;
  children: ReactNode;
}) {
  return (
    <details className="industry-research-audit">
      <summary>
        <span>{title}</span>
        {summary && <small>{summary}</small>}
      </summary>
      <div className="industry-research-audit__body">{children}</div>
    </details>
  );
}

function safeExternalUrl(value?: string): string | undefined {
  if (!value) return undefined;
  try {
    const url = new URL(value);
    return url.protocol === "http:" || url.protocol === "https:" ? url.toString() : undefined;
  } catch {
    return undefined;
  }
}

function nodeName(node: IndustryChainNode): string {
  return String(node.name || node.company || node.code || "未命名环节");
}

function SourceLabel({ source, url }: { source?: string; url?: string }) {
  const safeUrl = safeExternalUrl(url);
  if (!source && !safeUrl) return null;
  if (!safeUrl) return <Text type="secondary" style={{ fontSize: 11 }}>来源：{source}</Text>;
  return (
    <a href={safeUrl} target="_blank" rel="noreferrer" style={{ fontSize: 11 }}>
      来源：{source || "查看原文"}
    </a>
  );
}

function EvidenceTags({ ids }: { ids?: string[] }) {
  if (!ids?.length) return null;
  return (
    <div style={{ display: "flex", flexWrap: "wrap", gap: 4, marginTop: 6 }}>
      {ids.map((id) => <Tag key={id} style={{ margin: 0, fontSize: 10 }}>证据 {id}</Tag>)}
    </div>
  );
}

function ChainNodeCard({ node, framed = false }: { node: IndustryChainNode; framed?: boolean }) {
  const colors = useColors();
  return (
    <div className={`industry-chain-node${framed ? " is-framed" : ""}`}>
      <div style={{ display: "flex", justifyContent: "space-between", alignItems: "flex-start", gap: 8 }}>
        <Text strong style={{ minWidth: 0, overflowWrap: "anywhere" }}>{nodeName(node)}</Text>
        {node.code && <Tag style={{ margin: 0, flexShrink: 0 }}>{node.code}</Tag>}
      </div>
      {node.role && <Text style={{ display: "block", marginTop: 4, color: colors.primary, fontSize: 12 }}>{node.role}</Text>}
      {node.description && <Paragraph type="secondary" style={{ margin: "6px 0 0", fontSize: 12 }}>{node.description}</Paragraph>}
      {node.companies && node.companies.length > 0 && (
        <div style={{ display: "flex", flexWrap: "wrap", gap: 4, marginTop: 8 }}>
          {node.companies.map((company) => <Tag key={company} style={{ margin: 0 }}>{company}</Tag>)}
        </div>
      )}
      {(node.market_share || node.metric) && (
        <Text type="secondary" style={{ display: "block", marginTop: 6, fontSize: 11 }}>
          {[node.market_share, node.metric].filter(Boolean).join(" · ")}
        </Text>
      )}
      <SourceLabel source={node.source} url={node.source_url} />
      <EvidenceTags ids={node.evidence_ids} />
    </div>
  );
}

function ChainTier({
  label,
  title,
  items,
  accent,
}: {
  label: string;
  title: string;
  items: IndustryChainNode[];
  accent: string;
}) {
  return (
    <div className="industry-chain-tier" style={{ borderLeftColor: accent }}>
      <Text style={{ color: accent, fontSize: 11, fontWeight: 700, letterSpacing: "0.08em" }}>{label}</Text>
      <Text strong style={{ display: "block", margin: "4px 0 10px", overflowWrap: "anywhere" }}>{title}</Text>
      <div className="industry-chain-tier__nodes">
        {items.length > 0
          ? items.map((item, index) => <ChainNodeCard key={`${nodeName(item)}-${index}`} node={item} />)
          : <Text type="secondary" style={{ fontSize: 12 }}>暂无结构化环节</Text>}
      </div>
    </div>
  );
}

function InsightPanel({ title, items }: { title: string; items: IndustryChainInsight[] }) {
  const colors = useColors();
  if (items.length === 0) return null;
  const renderInsight = (item: IndustryChainInsight, index: number) => (
    <div key={`${item.title}-${index}`} className="industry-research-list__item">
      <Text strong>{item.title}</Text>
      <div style={{ display: "flex", gap: 4, marginTop: 4 }}>
        <Tag style={{ margin: 0, fontSize: 10 }}>
          {item.claim_type === "fact" ? "事实" : item.claim_type === "opinion" ? "观点" : "推断"}
        </Tag>
        <Tag style={{ margin: 0, fontSize: 10 }}>
          置信度 {item.confidence === "high" ? "高" : item.confidence === "low" ? "低" : "中"}
        </Tag>
      </div>
      {item.detail && <Paragraph type="secondary" style={{ margin: "4px 0 0", fontSize: 12 }}>{item.detail}</Paragraph>}
      {item.evidence && <Text style={{ display: "block", color: colors.primary, fontSize: 11 }}>观察：{item.evidence}</Text>}
      <SourceLabel source={item.source} url={item.source_url} />
      <EvidenceTags ids={item.evidence_ids} />
    </div>
  );
  return (
    <ResearchBlock title={title} className="is-fill">
      <div className="industry-research-list">
        {items.map(renderInsight)}
      </div>
    </ResearchBlock>
  );
}

function CompetitionPanel({ groups }: { groups: IndustryChainCompetitionGroup[] }) {
  if (groups.length === 0) return null;
  return (
    <ResearchBlock title="竞争格局">
      <Row gutter={[12, 12]}>
        {groups.map((group, groupIndex) => (
          <Col xs={24} lg={groups.length > 1 ? 12 : 24} key={`${group.market}-${groupIndex}`}>
            <div className="industry-research-group">
              <Text strong style={{ fontSize: 14 }}>{group.market}</Text>
              {group.summary && <Paragraph type="secondary" style={{ margin: "4px 0 12px", fontSize: 12 }}>{group.summary}</Paragraph>}
              <div className="industry-research-group__items">
                {group.companies.map((company, companyIndex) => (
                  <ChainNodeCard key={`${nodeName(company)}-${companyIndex}`} node={company} />
                ))}
              </div>
            </div>
          </Col>
        ))}
      </Row>
    </ResearchBlock>
  );
}

function SourcesPanel({ sources }: { sources: IndustryChainSource[] }) {
  if (sources.length === 0) return null;
  return (
    <AuditDisclosure title="数据来源与口径" summary={`${sources.length} 条来源`}>
      <div className="industry-source-list">
        {sources.map((source, index) => {
          const safeUrl = safeExternalUrl(source.url);
          const label = [source.publisher, source.date].filter(Boolean).join(" · ");
          return (
            <div key={`${source.title}-${index}`} className="industry-source-list__item">
              {safeUrl ? (
                <a href={safeUrl} target="_blank" rel="noreferrer" style={{ minWidth: 0, overflowWrap: "anywhere" }}>{source.title}</a>
              ) : <Text>{source.title}</Text>}
              {label && <Text type="secondary" style={{ flexShrink: 0, fontSize: 11 }}>{label}</Text>}
            </div>
          );
        })}
      </div>
    </AuditDisclosure>
  );
}

function EvidenceCatalogPanel({ evidence, stats }: { evidence: IndustryChainEvidence[]; stats?: IndustryChainEvidenceStats }) {
  if (!evidence.length) return null;
  return (
    <AuditDisclosure
      title="工具证据目录"
      summary={`${stats?.selected_count || evidence.length} 条合成证据`}
    >
      {stats && (stats.total_count || 0) > 0 && (
        <Text type="secondary" style={{ display: "block", marginBottom: 10, fontSize: 12 }}>
          共 {stats.total_count || 0} 次调用 · 去重后 {stats.unique_count || 0} 条 · 合成使用 {stats.selected_count || 0} 条
          {stats.failed_count ? ` · 失败 ${stats.failed_count} 条` : ""}
          {stats.prompt_characters ? ` · 上下文 ${stats.prompt_characters} 字符` : ""}
        </Text>
      )}
      <div style={{ display: "grid", gap: 10 }}>
        {evidence.map((item) => (
          <details key={item.evidence_id} className="industry-evidence-item">
            <summary style={{ display: "flex", flexWrap: "wrap", alignItems: "center", gap: 8, cursor: "pointer" }}>
              <Tag style={{ margin: 0 }}>{item.evidence_id}</Tag>
              <Text code>{item.tool_name}</Text>
              {item.provider && <Text type="secondary">{item.provider}</Text>}
              <Text strong>{item.title || "工具调用证据"}</Text>
              {item.status === "error" && <Tag color="error" style={{ margin: 0 }}>调用失败</Tag>}
              {item.truncated && <Tag color="warning" style={{ margin: 0 }}>已截断</Tag>}
            </summary>
            <div style={{ display: "grid", gap: 8, marginTop: 10 }}>
              {(item.published_at || item.fetched_at) && (
                <Text type="secondary" style={{ fontSize: 12 }}>
                  {[item.published_at && `发布：${item.published_at}`, item.fetched_at && `抓取：${item.fetched_at}`].filter(Boolean).join(" · ")}
                </Text>
              )}
              {item.source_urls?.length ? (
                <div style={{ display: "flex", flexWrap: "wrap", gap: 8 }}>
                  {item.source_urls.map((url, index) => {
                    const safeUrl = safeExternalUrl(url);
                    return safeUrl ? <a key={safeUrl} href={safeUrl} target="_blank" rel="noreferrer">原文 {index + 1}</a> : null;
                  })}
                </div>
              ) : null}
              {item.content_preview && <Paragraph type="secondary" style={{ margin: 0, fontSize: 12 }}>{item.content_preview}</Paragraph>}
              {item.error_message && <Text type="danger">{item.error_message}</Text>}
              {item.arguments && (
                <div>
                  <Text type="secondary" style={{ fontSize: 12 }}>调用参数</Text>
                  <pre style={{ margin: "4px 0 0", maxHeight: 140, overflow: "auto", whiteSpace: "pre-wrap", overflowWrap: "anywhere" }}>{item.arguments}</pre>
                </div>
              )}
            </div>
          </details>
        ))}
      </div>
    </AuditDisclosure>
  );
}

function ResearchQualityPanel({
  coverage,
  missingEvidence,
  conflicts,
}: {
  coverage?: IndustryChainCoverage;
  missingEvidence: string[];
  conflicts: IndustryChainConflict[];
}) {
  if (!coverage && missingEvidence.length === 0 && conflicts.length === 0) return null;
  const labels: Record<string, string> = {
    market: "市场",
    competition: "竞争",
    technology: "技术",
    chain: "产业链",
    companies: "公司",
    events: "事件",
  };
  const statusLabel = { complete: "完整", partial: "部分", missing: "缺失" } as const;
  const coverageCount = Object.keys(coverage || {}).length;
  return (
    <AuditDisclosure
      title="研究覆盖与证据缺口"
      summary={`${coverageCount} 项覆盖 · ${missingEvidence.length + conflicts.length} 项待核验`}
    >
      {coverage && (
        <div style={{ display: "flex", flexWrap: "wrap", gap: 6, marginBottom: missingEvidence.length || conflicts.length ? 12 : 0 }}>
          {Object.entries(coverage).map(([key, status]) => (
            (() => {
              const normalizedStatus: keyof typeof statusLabel = status === "complete" || status === "partial"
                ? status
                : "missing";
              return (
                <Tag key={key} color={normalizedStatus === "complete" ? "success" : normalizedStatus === "partial" ? "warning" : "error"} style={{ margin: 0 }}>
                  {labels[key] || key}：{statusLabel[normalizedStatus]}
                </Tag>
              );
            })()
          ))}
        </div>
      )}
      {missingEvidence.length > 0 && (
        <div style={{ marginBottom: conflicts.length ? 12 : 0 }}>
          <Text strong>缺失证据</Text>
          <ul style={{ margin: "6px 0 0", paddingLeft: 18 }}>{missingEvidence.map((item) => <li key={item}>{item}</li>)}</ul>
        </div>
      )}
      {conflicts.length > 0 && (
        <div>
          <Text strong>数据冲突</Text>
          <div style={{ display: "grid", gap: 8, marginTop: 6 }}>
            {conflicts.map((conflict, index) => (
              <div key={`${conflict.topic}-${index}`} style={{ padding: 8, border: "1px solid var(--c-border)", borderRadius: 6 }}>
                <Text>{conflict.topic}</Text>
                {conflict.values?.length ? <Text type="secondary" style={{ display: "block" }}>{conflict.values.join(" / ")}</Text> : null}
                {conflict.reason && <Text type="secondary" style={{ display: "block" }}>{conflict.reason}</Text>}
                <EvidenceTags ids={conflict.evidence_ids} />
              </div>
            ))}
          </div>
        </div>
      )}
    </AuditDisclosure>
  );
}

export default function IndustryResearchSections({ result }: { result: IndustryChainResult }) {
  const colors = useColors();
  const isNarrow = useMediaQuery("(max-width: 768px)");
  const marketMetrics = result.market_metrics ?? [];
  const competition = result.competition ?? [];
  const technologyRoutes = result.technology_routes ?? [];
  const trends = result.trends ?? [];
  const capitalMoves = result.capital_moves ?? [];
  const keyEvents = result.key_events ?? [];
  const driverInsights = result.driver_insights ?? [];
  const riskInsights = result.risk_insights ?? [];
  const hasChain = result.upstream.length > 0 || result.midstream.length > 0 || result.downstream.length > 0;

  const metricColumns: TableProps<IndustryChainMetric>["columns"] = [
    { title: "指标", dataIndex: "label", key: "label" },
    { title: "数据", dataIndex: "value", key: "value", render: (value, record) => <Text strong>{value}{record.growth ? ` · ${record.growth}` : ""}</Text> },
    { title: "期间", dataIndex: "period", key: "period", width: 120 },
    {
      title: "来源",
      key: "source",
      width: 150,
      render: (_, record) => <SourceLabel source={record.source} url={record.source_url} />,
    },
  ];

  return (
    <div className="industry-research-sections">
      {marketMetrics.length > 0 && (
        <ResearchBlock title="市场规模与增长">
          {isNarrow ? (
            <div className="industry-market-metrics">
              {marketMetrics.map((metric) => (
                <div key={`${metric.label}-${metric.period || "latest"}`} className="industry-market-metric">
                  <Text type="secondary" style={{ fontSize: 12 }}>{metric.label}</Text>
                  <Text strong style={{ display: "block", marginTop: 4, fontSize: 16 }}>{metric.value}</Text>
                  <Text type="secondary" style={{ fontSize: 11 }}>{[metric.period, metric.growth].filter(Boolean).join(" · ")}</Text>
                  <SourceLabel source={metric.source} url={metric.source_url} />
                  <EvidenceTags ids={metric.evidence_ids} />
                </div>
              ))}
            </div>
          ) : (
            <Table<IndustryChainMetric>
              columns={metricColumns}
              dataSource={marketMetrics}
              rowKey={(metric) => `${metric.label}-${metric.period || "latest"}`}
              pagination={false}
              size="small"
            />
          )}
        </ResearchBlock>
      )}

      <CompetitionPanel groups={competition} />

      {hasChain && (
        <ResearchBlock title="产业链地图">
          <div className="industry-chain-flow">
            <ChainTier label="UPSTREAM" title="上游供给" items={result.upstream} accent={colors.warning} />
            <div aria-hidden className="industry-chain-flow__arrow">→</div>
            <ChainTier label="CORE" title={result.name || "核心环节"} items={result.midstream} accent={colors.primary} />
            <div aria-hidden className="industry-chain-flow__arrow">→</div>
            <ChainTier label="DOWNSTREAM" title="下游需求" items={result.downstream} accent={colors.down} />
          </div>
        </ResearchBlock>
      )}

      <Row className="industry-research-grid" gutter={[16, 16]}>
        {technologyRoutes.length > 0 && <Col xs={24} lg={12}><InsightPanel title="技术与商业路线" items={technologyRoutes} /></Col>}
        {trends.length > 0 && <Col xs={24} lg={12}><InsightPanel title="关键趋势与催化剂" items={trends} /></Col>}
        {capitalMoves.length > 0 && <Col xs={24}><InsightPanel title="资本运作与产业动作" items={capitalMoves} /></Col>}
        {driverInsights.length > 0 && <Col xs={24} lg={12}><InsightPanel title="行业驱动" items={driverInsights} /></Col>}
        {riskInsights.length > 0 && <Col xs={24} lg={12}><InsightPanel title="风险提示" items={riskInsights} /></Col>}
      </Row>

      {keyEvents.length > 0 && (
        <ResearchBlock title="关键事件">
          <div className="industry-event-list">
            {keyEvents.map((event, index) => (
              <div key={`${event.date}-${event.title}-${index}`} className="industry-event-list__item">
                <Text style={{ color: colors.primary, fontSize: 12, fontWeight: 600 }}>{event.date || "时间待确认"}</Text>
                <div>
                  <Text strong>{event.title}</Text>
                  {event.impact && <Paragraph type="secondary" style={{ margin: "4px 0 0", fontSize: 12 }}>{event.impact}</Paragraph>}
                  <SourceLabel source={event.source} url={event.source_url} />
                  <EvidenceTags ids={event.evidence_ids} />
                </div>
              </div>
            ))}
          </div>
        </ResearchBlock>
      )}

      {result.key_stocks.length > 0 && (
        <ResearchBlock title={result.research_scope?.company_scope === "all_public" ? "重点公司" : "A 股重点公司"}>
          <Row gutter={[12, 12]}>
            {result.key_stocks.map((stock, index) => (
              <Col xs={24} md={12} xl={8} key={`${nodeName(stock)}-${index}`}>
                <ChainNodeCard node={stock} framed />
              </Col>
            ))}
          </Row>
        </ResearchBlock>
      )}

      {driverInsights.length === 0 && riskInsights.length === 0 && (result.drivers.length > 0 || result.risks.length > 0) && (
        <Row className="industry-research-grid" gutter={[16, 16]}>
          {result.drivers.length > 0 && (
            <Col xs={24} lg={12}>
              <ResearchBlock title="行业驱动" className="is-fill">
                <ul style={{ margin: 0, paddingLeft: 18 }}>{result.drivers.map((driver) => <li key={driver} style={{ marginBottom: 8 }}>{driver}</li>)}</ul>
              </ResearchBlock>
            </Col>
          )}
          {result.risks.length > 0 && (
            <Col xs={24} lg={12}>
              <ResearchBlock title="风险提示" className="is-fill">
                <ul style={{ margin: 0, paddingLeft: 18 }}>{result.risks.map((risk) => <li key={risk} style={{ marginBottom: 8, color: colors.textSecondary }}>{risk}</li>)}</ul>
              </ResearchBlock>
            </Col>
          )}
        </Row>
      )}

    </div>
  );
}

export function IndustryResearchAudit({ result }: { result: IndustryChainResult }) {
  return (
    <div className="industry-report__section-content">
      <ResearchQualityPanel
        coverage={result.coverage}
        missingEvidence={result.missing_evidence || []}
        conflicts={result.conflicts || []}
      />
      <SourcesPanel sources={result.sources || []} />
      <EvidenceCatalogPanel evidence={result.evidence_catalog || []} stats={result.evidence_stats} />
    </div>
  );
}
