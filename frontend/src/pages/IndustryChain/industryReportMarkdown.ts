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

  return lines.join("\n");
}
