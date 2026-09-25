import { Tag } from "antd";
import type { IndustryChainResult } from "../../types/stock";

export default function IndustryResearchTheses({ result }: { result: IndustryChainResult }) {
  if (!result.research_theses?.length) return null;
  const join = (items?: string[]) => items?.length ? items.join("；") : "待补充";
  return <section className="industry-decision-research" aria-labelledby="industry-theses-heading">
    <h3 id="industry-theses-heading">核心研究判断</h3>
    <p>从经营矛盾到公司兑现。以下是有条件的研究推断，不代表事实核实或收益承诺。</p>
    {result.research_theses.map((thesis, index) => <article key={`${thesis.title}-${index}`}>
      <h4>{thesis.title}</h4>
      <Tag color={thesis.verification_status === "quote_matched" ? "blue" : "orange"}>
        {thesis.verification_status === "quote_matched" ? "前提原文已匹配 · 推导待复核" : "前提证据不足 · 待验证"}
      </Tag>
      <p>{thesis.detail}</p>
      <p><strong>上下游路径：</strong>{thesis.chain_path?.length ? thesis.chain_path.join(" → ") : "尚未建立有向跨环节路径"}</p>
      {(thesis.verification_notes ?? []).filter(note => note.includes("路径") || note.includes("传导边")).map(note => <p key={note}>{note}</p>)}
      <p><strong>传导机制：</strong>{thesis.mechanism || "待补充"}</p>
      <p><strong>成立条件：</strong>{join(thesis.conditions)}</p>
      <p><strong>反向证据：</strong>{thesis.counter_evidence || "本次未取得反向证据"}</p>
      <p><strong>失效条件：</strong>{thesis.invalidation || "待补充"}</p>
      <p><strong>跟踪指标：</strong>{join(thesis.tracking_metrics)}</p>
      {thesis.beneficiaries?.length ? <p><strong>相关公司（非投资推荐）：</strong>{join(thesis.beneficiaries)}</p> : null}
      {(thesis.citations ?? []).map((citation, i) => <blockquote key={i} style={{ marginInline: 12, overflowWrap: "anywhere" }}>{citation.quote}</blockquote>)}
    </article>)}
  </section>;
}
