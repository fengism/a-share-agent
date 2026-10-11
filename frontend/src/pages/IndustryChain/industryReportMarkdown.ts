import type { IndustryChainResult } from "../../types/stock";

export function buildIndustryReportMarkdown(
  result: IndustryChainResult,
  activeName?: string,
): string {
  const title = result.topic_resolution?.normalized_name || result.name || activeName || "产业链研究报告";
  const lines: string[] = [];
  lines.push(`# ${title} 产业链投研报告`);
  lines.push("");
  if (result.research_scope?.as_of_date) {
    lines.push(`> 报告日期：${result.research_scope.as_of_date}`);
  }
  lines.push("");

  if (result.llm_review) {
    lines.push(result.llm_review);
    return lines.join("\n");
  }

  if (result.summary) {
    lines.push("## 一、产业研判与核心观点");
    lines.push("");
    lines.push(result.summary);
    lines.push("");
  }

  if (result.research_theses && result.research_theses.length > 0) {
    lines.push("## 二、核心研究论点");
    lines.push("");
    result.research_theses.forEach((t, i) => {
      lines.push(`### ${i + 1}. ${t.title}`);
      if (t.detail) lines.push(t.detail);
      lines.push("");
    });
  }

  if (result.key_stocks && result.key_stocks.length > 0) {
    lines.push("## 三、核心龙头标的");
    lines.push("");
    result.key_stocks.forEach((stock, i) => {
      lines.push(`${i + 1}. **${stock.name}** (${stock.code}) - ${stock.role || "产业链核心企业"}`);
    });
    lines.push("");
  }

  const stages = [
    { label: "上游", nodes: result.upstream },
    { label: "中游", nodes: result.midstream },
    { label: "下游", nodes: result.downstream },
  ];
  const hasNodes = stages.some((s) => s.nodes && s.nodes.length > 0);
  if (hasNodes) {
    lines.push("## 四、上下游环节与价值分布");
    lines.push("");
    stages.forEach(({ label, nodes }) => {
      if (!nodes || nodes.length === 0) return;
      lines.push(`### ${label}核心环节`);
      lines.push("");
      lines.push("| 环节名称 | 核心角色与职能 | 代表公司/标的 | 市场地位/份额 |");
      lines.push("| --- | --- | --- | --- |");
      nodes.forEach((node) => {
        const name = node.name || node.company || node.code || "未命名环节";
        const role = (node.role || node.description || "-").replace(/\|/g, "\\|");
        const companies = (node.companies && node.companies.length > 0 ? node.companies.join("、") : node.code || "-").replace(/\|/g, "\\|");
        const market = (node.market_share || node.metric || "-").replace(/\|/g, "\\|");
        lines.push(`| **${name}** | ${role} | ${companies} | ${market} |`);
      });
      lines.push("");
    });
  }

  if (result.relationships && result.relationships.length > 0) {
    lines.push("## 五、产业链传导机制与核心假设");
    lines.push("");
    result.relationships.forEach((rel, i) => {
      const direction = rel.impact_direction === "positive" ? "正向传导" : rel.impact_direction === "negative" ? "负向传导" : "定性传导";
      lines.push(`### ${i + 1}. ${rel.source_node} → ${rel.target_node}（${direction}）`);
      if (rel.driver) lines.push(`- **驱动变化**：${rel.driver}`);
      if (rel.detail || rel.title) lines.push(`- **传导机制**：${rel.detail || rel.title}`);
      if (rel.conditions && rel.conditions.length > 0) lines.push(`- **成立条件**：${rel.conditions.join("；")}`);
      if (rel.invalidation) lines.push(`- **失效风险**：${rel.invalidation}`);
      lines.push("");
    });
  }

  if (result.risks && result.risks.length > 0) {
    lines.push("## 六、潜在风险与跟踪提示");
    lines.push("");
    result.risks.forEach((risk, i) => {
      lines.push(`${i + 1}. ${risk}`);
    });
    lines.push("");
  }

  return lines.join("\n");
}
