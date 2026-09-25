import { useState } from "react";
import { Select, Table, Tag } from "antd";
import type { IndustryChainResult } from "../../types/stock";
import EvidenceLinkedText from "./EvidenceLinkedText";
import { buildStockAnalysisUrl, buildStockProfileUrl } from "../../utils/stockLinks";

const RELATION = { supply: "供货", purchase: "采购", substitute: "替代", compete: "竞争", transmission: "定性传导" };
const RELEVANCE = { unverified: "待验证", concept: "概念布局", business: "业务相关（待复核）", earnings: "收入相关（待复核）" };
const DIRECTION = { positive: "正向", negative: "负向", mixed: "双向", unknown: "尚不明确" };

export default function IndustryDecisionResearch({ result }: { result: IndustryChainResult }) {
  const [selected, setSelected] = useState<string[]>([]);
  const companies = result.key_stocks.map((node, index) => ({
    ...node, key: `${node.code || node.name || "company"}-${index}`,
  }));
  const filtered = selected.length ? companies.filter(node => selected.includes(node.key)) : companies;
  const join = (items?: string[]) => items?.length ? items.join("；") : "待补充";
  return <section className="industry-decision-research" aria-label="关系传导与公司验证">
    {!!result.relationships?.length && <>
      <h3>关系与利润传导</h3>
      <p>以下为证据线索和条件假设；正负方向针对目标节点，不作定量盈利预测。</p>
      <ul>{result.relationships.map((edge, index) => <li key={`${edge.source_node}-${edge.target_node}-${index}`}>
        <strong>{edge.source_node} → {edge.target_node}</strong>{" "}
        <Tag>{RELATION[edge.relation_type]}</Tag><Tag>{DIRECTION[edge.impact_direction || "unknown"]}</Tag>
        <Tag color="orange">{edge.verification_status === "quote_matched" ? "原文片段匹配，仍待复核" : "关系待验证"}</Tag>
        {edge.relation_type === "transmission" && <>
          <p><strong>冲击/变化：</strong>{edge.driver || "待补证"}</p>
          <p><strong>目标经营指标：</strong>{edge.target_metric || "待补证"}</p>
        </>}
        <p><strong>传导机制：</strong>{edge.detail || edge.title}</p>
        {edge.relation_type === "transmission" && <>
          <p><strong>传导时滞：</strong>{edge.time_lag || "未知，不假设即时兑现"}</p>
          <p><strong>跟踪指标：</strong>{join(edge.tracking_metrics)}</p>
        </>}
        <p>成立条件：{join(edge.conditions)}；失效条件：{edge.invalidation || "待补充"}</p>
        <EvidenceLinkedText text={(edge.evidence_ids ?? []).map(id => `证据 ${id}`).join(" · ")} evidenceCatalog={result.evidence_catalog} />
      </li>)}</ul>
    </>}
    {!!companies.length && <>
      <h3>公司业务相关度与兑现条件</h3>
      <p>概念布局不等于业绩贡献；原文匹配不代表已独立核实公司分类或收入占比。</p>
      <Select mode="multiple" aria-label="选择对比公司" placeholder="选择公司横向比较（默认全部）"
        style={{ width: "100%", marginBottom: 12 }} value={selected} onChange={setSelected}
        options={companies.map(node => ({ value: node.key, label: node.name || node.company || node.code }))} />
      <Table size="small" pagination={false} scroll={{ x: 1100 }} dataSource={filtered} columns={[
        { title: "公司 / 环节", key: "company", width: 160, render: (_, node) => <><strong>{node.name || node.company || node.code}</strong><p>{node.role || "待补充"}</p>{node.code && <p><a href={buildStockProfileUrl(node.code)}>公司资料</a>{" · "}<a href={buildStockAnalysisUrl(node.code)}>深入研究</a></p>}</> },
        { title: "业务相关度", key: "relevance", width: 150, render: (_, node) => RELEVANCE[node.business_relevance || "unverified"] },
        { title: "相关收入占比", key: "revenue", width: 130, render: (_, node) => node.revenue_share ? `${node.revenue_share}（${node.revenue_period || "统计期待核实"}）` : "未验证" },
        { title: "受益路径", dataIndex: "benefit_path", width: 180, render: value => value || "待补充" },
        { title: "兑现条件", key: "conditions", width: 170, render: (_, node) => join(node.realization_conditions) },
        { title: "失效条件", key: "invalidation", width: 170, render: (_, node) => join(node.invalidation_conditions) },
        { title: "跟踪指标", key: "tracking", width: 170, render: (_, node) => join(node.tracking_metrics) },
      ]} />
    </>}
  </section>;
}
