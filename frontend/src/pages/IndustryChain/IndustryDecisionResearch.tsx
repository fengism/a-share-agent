import { useState } from "react";
import { useNavigate } from "react-router-dom";
import { Button, Select, Table, Tag } from "antd";
import type { IndustryChainResult } from "../../types/stock";
import EvidenceLinkedText from "./EvidenceLinkedText";
import { buildStockAnalysisUrl, buildStockProfileUrl } from "../../utils/stockLinks";

function useSafeNavigate() {
  try {
    return useNavigate();
  } catch {
    return (path: string) => {
      if (typeof window !== "undefined") {
        window.location.href = path;
      }
    };
  }
}

const RELATION = { supply: "供货", purchase: "采购", substitute: "替代", compete: "竞争", transmission: "定性传导" };
const RELEVANCE = { unverified: "待验证", concept: "概念布局", business: "业务相关（待复核）", earnings: "收入相关（待复核）" };
const RELEVANCE_COLOR: Record<string, string> = { unverified: "default", concept: "warning", business: "processing", earnings: "success" };
const DIRECTION = { positive: "正向", negative: "负向", mixed: "双向", unknown: "尚不明确" };

export default function IndustryDecisionResearch({ result }: { result: IndustryChainResult }) {
  const navigate = useSafeNavigate();
  const [selected, setSelected] = useState<string[]>([]);
  const companies = result.key_stocks.map((node, index) => ({
    ...node, key: `${node.code || node.name || "company"}-${index}`,
  }));
  const filtered = selected.length ? companies.filter(node => selected.includes(node.key)) : companies;
  const join = (items?: string[]) => items?.length ? items.join("；") : "待补充";

  const listedCount = companies.filter(c => !!c.code).length;
  const highRelevanceCount = companies.filter(c => c.business_relevance === "earnings" || c.business_relevance === "business").length;
  const powerLabelMap: Record<string, { text: string; color: string }> = {
    high: { text: "强", color: "green" },
    medium: { text: "中", color: "blue" },
    low: { text: "弱", color: "orange" },
    unverified: { text: "待验证", color: "default" },
  };

  return <section className="industry-decision-research" aria-label="关系传导与公司验证">
    {!!result.value_distribution?.length && (
      <div style={{ marginBottom: 20 }}>
        <h3>价值链 BOM 成本拆解与利润池分配</h3>
        <p>剖析产业链各环节单机/系统价值量占比、毛利率区间与议价定价权，锁定高壁垒利润池核心环节。</p>
        <Table
          size="small"
          pagination={false}
          scroll={{ x: 800 }}
          dataSource={result.value_distribution.map((item, idx) => ({ ...item, key: `vd-${idx}` }))}
          columns={[
            { title: "环节/核心组件", dataIndex: "segment", width: 140, render: (v) => <strong>{v}</strong> },
            { title: "BOM 成本占比", dataIndex: "cost_share", width: 120, render: (v) => v || "—" },
            { title: "毛利率区间", dataIndex: "gross_margin_range", width: 120, render: (v) => v || "—" },
            { title: "利润池占比", dataIndex: "profit_share", width: 130, render: (v) => <span style={{ color: "var(--c-success, #16a34a)" }}>{v || "—"}</span> },
            {
              title: "议价定价权",
              dataIndex: "pricing_power",
              width: 100,
              render: (v) => {
                const cfg = powerLabelMap[v || ""] || { text: v || "—", color: "default" };
                return <Tag color={cfg.color}>{cfg.text}</Tag>;
              },
            },
            { title: "技术门槛与机制说明", dataIndex: "detail", render: (v) => v || "待补充" },
          ]}
        />
      </div>
    )}

    {!!result.expectation_divergences?.length && (
      <div style={{ marginBottom: 20 }}>
        <h3>市场一致预期 vs 本次研究分歧（预期差推演）</h3>
        <p>提炼买方核心关注的预期差，对比市场共识与审慎推断，并明确后续关键验证指标。</p>
        <div className="industry-expectation-divergences">
          {result.expectation_divergences.map((item, idx) => (
            <div
              key={`exp-${idx}`}
              style={{
                background: "var(--c-bg-card, #ffffff)",
                border: "1px solid var(--c-border-light, #e2e8f0)",
                borderRadius: 8,
                padding: "var(--c-pad-card, 16px 18px)",
              }}
            >
              <div style={{ fontWeight: 700, color: "var(--c-text-primary, #0f172a)", marginBottom: 6 }}>
                ⚡ 焦点：{item.topic}
              </div>
              <div style={{ fontSize: 12, color: "var(--c-text-secondary, #64748b)", marginBottom: 4 }}>
                • <b>市场一致预期：</b>{item.consensus || "广泛乐观/悲观计价"}
              </div>
              <div style={{ fontSize: 12, color: "var(--c-warning, #b45309)", marginBottom: 4 }}>
                • <b>本次审慎推断：</b>{item.divergence}
              </div>
              {item.catalyst_trigger && (
                <div style={{ fontSize: 11, color: "var(--c-primary, #0284c7)" }}>
                  • 核心验证窗口：{item.catalyst_trigger}
                </div>
              )}
            </div>
          ))}
        </div>
      </div>
    )}
    {!!result.relationships?.length && <>
      <h3>关系与利润传导</h3>
      <p>以下为证据线索和条件假设；正负方向针对目标节点，不作定量盈利预测。</p>
      <ul style={{ listStyle: "none", padding: 0, margin: "12px 0 16px" }}>{result.relationships.map((edge, index) => <li key={`${edge.source_node}-${edge.target_node}-${index}`} style={{ background: "var(--c-bg-card, #ffffff)", border: "1px solid var(--c-border-light, #e2e8f0)", borderRadius: 8, padding: "var(--c-pad-card, 16px 18px)", marginBottom: 10 }}>
        <div style={{ display: "flex", alignItems: "center", gap: 6, flexWrap: "wrap", marginBottom: 4 }}>
          <strong>{edge.source_node} → {edge.target_node}</strong>{" "}
          <Tag>{RELATION[edge.relation_type]}</Tag><Tag>{DIRECTION[edge.impact_direction || "unknown"]}</Tag>
          <Tag color="orange">{edge.verification_status === "quote_matched" ? "原文片段匹配，仍待复核" : "关系待验证"}</Tag>
        </div>
        {edge.relation_type === "transmission" && <>
          <p style={{ margin: "4px 0" }}><strong>冲击/变化：</strong>{edge.driver || "待补证"}</p>
          <p style={{ margin: "4px 0" }}><strong>目标经营指标：</strong>{edge.target_metric || "待补证"}</p>
        </>}
        <p style={{ margin: "4px 0" }}><strong>传导机制：</strong>{edge.detail || edge.title}</p>
        {edge.relation_type === "transmission" && <>
          <p style={{ margin: "4px 0" }}><strong>传导时滞：</strong>{edge.time_lag || "未知，不假设即时兑现"}</p>
          <p style={{ margin: "4px 0" }}><strong>跟踪指标：</strong>{join(edge.tracking_metrics)}</p>
        </>}
        <p style={{ margin: "4px 0", color: "var(--c-text-secondary, #64748b)" }}>成立条件：{join(edge.conditions)}；失效条件：{edge.invalidation || "待补充"}</p>
        <div style={{ marginTop: 4 }}>
          <EvidenceLinkedText text={(edge.evidence_ids ?? []).map(id => `证据 ${id}`).join(" · ")} evidenceCatalog={result.evidence_catalog} />
        </div>
      </li>)}</ul>
    </>}
    {!!companies.length && <>
      <h3>公司业务相关度与兑现条件</h3>
      <p>概念布局不等于业绩贡献；原文匹配不代表已独立核实公司分类或收入占比。</p>
      <div style={{ display: "flex", gap: 8, alignItems: "center", marginBottom: 12, flexWrap: "wrap" }}>
        <Select mode="multiple" aria-label="选择对比公司" placeholder="选择公司横向比较（默认全部）"
          style={{ flex: "1 1 220px", minWidth: 0, width: "100%" }} value={selected} onChange={setSelected}
          options={companies.map(node => ({ value: node.key, label: node.name || node.company || node.code }))} />
        {listedCount > 0 && (
          <Button size="small" onClick={() => setSelected(companies.filter(c => !!c.code).map(c => c.key))}>
            仅看上市标的 ({listedCount})
          </Button>
        )}
        {highRelevanceCount > 0 && (
          <Button size="small" onClick={() => setSelected(companies.filter(c => c.business_relevance === "earnings" || c.business_relevance === "business").map(c => c.key))}>
            仅看实质/收入相关 ({highRelevanceCount})
          </Button>
        )}
        {selected.length > 0 && (
          <Button size="small" onClick={() => setSelected([])}>
            清除对比（共 {companies.length} 家，已选 {selected.length} 家）
          </Button>
        )}
      </div>
      <Table size="small" pagination={false} scroll={{ x: 1390 }} dataSource={filtered} columns={[
        { title: "公司 / 环节", key: "company", width: 170, render: (_, node) => (
          <>
            <strong>{node.name || node.company || node.code}</strong>
            <p style={{ margin: "2px 0 4px", fontSize: 12, color: "var(--c-text-secondary, #666)" }}>{node.role || "待补充"}</p>
            {node.code && (
              <div style={{ display: "flex", gap: 6, flexWrap: "wrap", alignItems: "center" }}>
                <Tag
                  color={node.code.length === 5 ? "processing" : "cyan"}
                  style={{ cursor: "pointer", margin: 0 }}
                  onClick={() => navigate(buildStockProfileUrl(node.code!))}
                  title="点击查看公司资料"
                >
                  {node.code} 资料 ↗
                </Tag>
                <a
                  href={buildStockAnalysisUrl(node.code)}
                  onClick={(e) => {
                    e.preventDefault();
                    navigate(buildStockAnalysisUrl(node.code!));
                  }}
                  style={{ fontSize: 12 }}
                >
                  深度研究 ↗
                </a>
              </div>
            )}
          </>
        ) },
        {
          title: "当前估值 / 市值",
          key: "valuation",
          width: 140,
          render: (_, node) => {
            const hasValuation = Boolean(node.pe || node.pb || node.total_market_cap || node.price_change);
            if (!hasValuation) return <span style={{ color: "var(--c-text-muted, #999)" }}>—</span>;
            return (
              <div style={{ fontSize: 12 }}>
                {node.price_change && <div>现价: <strong>{String(node.price_change)}</strong></div>}
                {node.total_market_cap && <div>市值: <span>{String(node.total_market_cap)}</span></div>}
                {(node.pe || node.pb) && (
                  <div style={{ color: "var(--c-text-secondary, #666)" }}>
                    {node.pe ? `PE: ${String(node.pe)}` : ""}
                    {node.pe && node.pb ? " · " : ""}
                    {node.pb ? `PB: ${String(node.pb)}` : ""}
                  </div>
                )}
                {node.pe_percentile && (
                  <div style={{ fontSize: 11, color: "var(--c-primary, #0284c7)", marginTop: 2 }}>
                    分位: {String(node.pe_percentile)}
                  </div>
                )}
              </div>
            );
          },
        },
        {
          title: "资本回报 / 增速",
          key: "roe_growth",
          width: 160,
          render: (_, node) => {
            const hasRoeOrGrowth = Boolean(node.roe || node.growth_rate);
            if (!hasRoeOrGrowth) return <span style={{ color: "var(--c-text-muted, #999)" }}>—</span>;
            return (
              <div style={{ fontSize: 12 }}>
                {node.roe && <div>ROE: <strong style={{ color: "var(--c-primary, #0284c7)" }}>{String(node.roe)}</strong></div>}
                {node.growth_rate && <div style={{ color: "var(--c-text-secondary, #666)", marginTop: 2 }}>{String(node.growth_rate)}</div>}
              </div>
            );
          },
        },
        {
          title: "业务相关度",
          key: "relevance",
          width: 150,
          render: (_, node) => {
            const relKey = node.business_relevance || "unverified";
            return <Tag color={RELEVANCE_COLOR[relKey] || "default"}>{RELEVANCE[relKey]}</Tag>;
          },
        },
        { title: "相关收入占比", key: "revenue", width: 130, render: (_, node) => node.revenue_share ? `${node.revenue_share}（${node.revenue_period || "统计期待核实"}）` : "未验证" },
        {
          title: "出海与海外占比",
          key: "overseas",
          width: 150,
          render: (_, node) =>
            node.overseas_share ? (
              <Tag color="cyan" style={{ fontSize: 11, margin: 0 }}>
                {String(node.overseas_share)}
              </Tag>
            ) : (
              <span style={{ color: "var(--c-text-muted, #999)" }}>—</span>
            ),
        },
        { title: "受益路径", dataIndex: "benefit_path", width: 180, render: value => value || "待补充" },
        {
          title: "机构一致预期",
          dataIndex: "consensus_forecast",
          width: 190,
          render: (value) => (value ? <span style={{ fontSize: 12, color: "var(--c-primary, #0284c7)" }}>{String(value)}</span> : "待覆盖"),
        },
        {
          title: "竞争壁垒 / 毛利",
          key: "moat_margin",
          width: 170,
          render: (_, node) => (
            <div style={{ fontSize: 12 }}>
              {node.gross_margin && <div>毛利率: <strong style={{ color: "var(--c-primary, #0284c7)" }}>{String(node.gross_margin)}</strong></div>}
              {node.moat ? <div>{String(node.moat)}</div> : !node.gross_margin ? "待补充" : null}
            </div>
          ),
        },
        {
          title: "业绩利润弹性",
          dataIndex: "eps_elasticity",
          width: 160,
          render: (value) => (value ? <span style={{ color: "var(--c-warning, #d97706)" }}>{String(value)}</span> : "待测算"),
        },
        { title: "兑现条件", key: "conditions", width: 170, render: (_, node) => join(node.realization_conditions) },
        {
          title: "失效条件 / 风险",
          key: "invalidation",
          width: 180,
          render: (_, node) => (
            <div style={{ fontSize: 12 }}>
              {node.restricted_risk && (
                <div style={{ color: "var(--c-danger, #dc2626)", marginBottom: 4 }}>
                  ⚠️ {String(node.restricted_risk)}
                </div>
              )}
              <div>{join(node.invalidation_conditions)}</div>
            </div>
          ),
        },
        { title: "跟踪指标", key: "tracking", width: 170, render: (_, node) => join(node.tracking_metrics) },
      ]} />
    </>}
  </section>;
}
