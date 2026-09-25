import { useState } from "react";
import { Collapse, Empty, Radio, Tag } from "antd";
import type { IndustryChainClaim, IndustryChainResult } from "../../types/stock";
import EvidenceLinkedText from "./EvidenceLinkedText";

interface ClaimEntry { label: string; section: string; claim: IndustryChainClaim }

function claimEntries(result: IndustryChainResult): ClaimEntry[] {
  const nodes = (section: string, rows: IndustryChainResult["key_stocks"] = []): ClaimEntry[] => rows.map(claim => ({
    label: claim.name || claim.company || claim.code || "节点", section, claim,
  }));
  const insights = (section: string, rows: Array<IndustryChainClaim & { title: string }> = []): ClaimEntry[] => rows.map(claim => ({
    label: claim.title, section, claim,
  }));
  return [
    ...(result.market_metrics ?? []).map(claim => ({ label: claim.label, section: "市场指标", claim })),
    ...insights("核心判断", result.research_theses),
    ...nodes("重点公司", result.key_stocks), ...nodes("上游", result.upstream),
    ...nodes("中游", result.midstream), ...nodes("下游", result.downstream),
    ...(result.competition ?? []).flatMap(group => nodes(`竞争 · ${group.market}`, group.companies)),
    ...insights("驱动", result.driver_insights), ...insights("风险", result.risk_insights),
    ...insights("技术", result.technology_routes), ...insights("趋势", result.trends),
    ...insights("资本", result.capital_moves), ...insights("事件", result.key_events),
    ...insights("关系", result.relationships),
  ];
}

function trustedCitationUrl(value?: string) {
  try {
    const url = new URL(value || "");
    return ["http:", "https:"].includes(url.protocol) && !url.username && !url.password ? url.href : undefined;
  } catch { return undefined; }
}

export default function IndustryEvidenceChecks({ result }: { result: IndustryChainResult }) {
  const [filter, setFilter] = useState("all");
  const [basisFilter, setBasisFilter] = useState("all");
  const claims = claimEntries(result);
  if (!claims.length) return null;
  const matched = claims.filter(({ claim }) => claim.verification_status === "quote_matched").length;
  const basisOf = (claim: IndustryChainClaim) => claim.claim_type === "inference" || claim.claim_type === "opinion" ? claim.claim_type : claim.evidence_basis || "disclosed";
  const basisLabels = { disclosed: "事实陈述（仍需核实）", forecast: "来源机构预测", inference: "研究推断", opinion: "观点" };
  const visible = claims.filter(({ claim }) => basisFilter === "all" || basisOf(claim) === basisFilter).filter(({ claim }) => filter === "all" || (filter === "matched") === (claim.verification_status === "quote_matched"));
  return <Collapse style={{ marginBottom: 16 }} items={[{
    key: "checks", label: "关键结论核验 · 原文匹配不等于事实核实",
    children: <>
      <p>共 {claims.length} 项 · 原文匹配 {matched} 项 · 待验证 {claims.length - matched} 项。摘要与产业定位未做逐句核验，不计入本统计。</p>
      <Radio.Group aria-label="核验状态筛选" value={filter} onChange={event => setFilter(event.target.value)}
        options={[{ label: "全部", value: "all" }, { label: "只看待验证", value: "unverified" }, { label: "只看原文匹配", value: "matched" }]} />
      <div style={{ marginBlock: 12 }}>
        <Radio.Group aria-label="判断性质筛选" value={basisFilter} onChange={event => setBasisFilter(event.target.value)}
          options={[{ label: "全部性质", value: "all" }, ...Object.entries(basisLabels).map(([value, label]) => ({ value, label }))]} />
      </div>
      {result.verification_repair?.note && <p>{result.verification_repair.note}</p>}
      <p>研究推断核对的是事实前提，不是证明推导成立；机构预测不等于已实现值。旧报告未记录性质时按事实陈述展示，不补认定为已核实。</p>
      {!visible.length ? <Empty image={Empty.PRESENTED_IMAGE_SIMPLE} description="当前筛选下没有结论" /> :
        <ul>{visible.map(({ label, section, claim }, index) => <li key={`${section}-${label}-${index}`}>
          <Tag>{section}</Tag><Tag>{basisLabels[basisOf(claim)]}</Tag><strong>{label}</strong>{" "}
          <Tag color={claim.verification_status === "quote_matched" ? "blue" : "orange"}>
            {claim.verification_status === "quote_matched" ? "原文片段已匹配" : "待验证"}
          </Tag>
          {(claim.citations ?? []).map((citation, i) => {
            const url = trustedCitationUrl(citation.source_url);
            const catalog = (result.evidence_catalog ?? []).find(item => item.evidence_id === citation.evidence_id);
            return <blockquote key={i} style={{ marginInline: 12, overflowWrap: "anywhere" }}>
              {citation.quote}
              {citation.location && <small> · 提供的位置（未独立核验）：{citation.location}</small>}
              {" · "}{url ? <a href={url} target="_blank" rel="noreferrer">查看匹配原文</a>
                : catalog?.source_urls?.length === 1
                  ? <EvidenceLinkedText text={`证据 ${citation.evidence_id}`} evidenceCatalog={result.evidence_catalog} />
                  : <span>原文链接未唯一定位</span>}
              {catalog?.published_at && <small> · 材料发布：{catalog.published_at}（不等于数据统计期）</small>}
            </blockquote>;
          })}
          {(claim.verification_notes ?? []).map(note => <p key={note}>{note}</p>)}
        </li>)}</ul>}
    </>,
  }]} />;
}
