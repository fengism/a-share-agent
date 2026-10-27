import type { IndustryChainResult } from "../../types/stock";

export function buildIndustryReportMarkdown(
  result: IndustryChainResult,
  activeName?: string,
): string {
  if (result.llm_review && result.llm_review.trim().startsWith("# ")) {
    return result.llm_review.trim();
  }

  const title = result.topic_resolution?.normalized_name || result.name || activeName || "产业链研究报告";
  const lines: string[] = [];
  lines.push(`# ${title} 产业链投研报告`);
  lines.push("");
  if (result.research_scope?.as_of_date) {
    lines.push(`> 报告日期：${result.research_scope.as_of_date}`);
  }
  lines.push("");

  if (result.llm_review) {
    lines.push(result.llm_review.trim());
    return lines.join("\n");
  }

  if (result.summary) {
    lines.push("## 一、产业研判与核心观点");
    lines.push("");
    lines.push(result.summary);
    if (result.positioning) {
      lines.push("");
      lines.push(`**产业定位：** ${result.positioning}`);
    }
    lines.push("");
  }

  if (result.value_distribution && result.value_distribution.length > 0) {
    lines.push("### 价值链 BOM 拆解与利润池分配");
    lines.push("");
    lines.push("| 环节/核心组件 | BOM成本占比 | 毛利率区间 | 利润池占比 | 议价定价权 | 价值与竞争机制 |");
    lines.push("| --- | --- | --- | --- | --- | --- |");
    const powerMap: Record<string, string> = {
      high: "强",
      medium: "中",
      low: "弱",
      unverified: "待验证",
    };
    result.value_distribution.forEach((v) => {
      const power = powerMap[v.pricing_power || ""] || v.pricing_power || "-";
      lines.push(
        `| **${v.segment}** | ${v.cost_share || "-"} | ${v.gross_margin_range || "-"} | ${v.profit_share || "-"} | ${power} | ${v.detail || "-"} |`,
      );
    });
    lines.push("");
  }

  const cycle = result.cycle_analysis;
  if (
    cycle &&
    (cycle.stage ||
      cycle.capacity_utilization ||
      cycle.expansion_lead_time ||
      cycle.inflection_point ||
      cycle.pass_through_ability)
  ) {
    lines.push("### 供需格局、周期定位与成本顺价机制");
    lines.push("");
    if (cycle.stage) lines.push(`- **周期所处阶段**：${cycle.stage}`);
    if (cycle.capacity_utilization) lines.push(`- **开工/产能利用率**：${cycle.capacity_utilization}`);
    if (cycle.expansion_lead_time) lines.push(`- **扩产与认证周期**：${cycle.expansion_lead_time}`);
    if (cycle.inflection_point) lines.push(`- **供需拐点推演**：${cycle.inflection_point}`);
    if (cycle.pass_through_ability) lines.push(`- **顺价能力与毛利弹性**：${cycle.pass_through_ability}`);
    lines.push("");
  }

  if (result.expectation_divergences && result.expectation_divergences.length > 0) {
    lines.push("### 市场一致预期 vs 本次研究分歧（预期差推演）");
    lines.push("");
    result.expectation_divergences.forEach((d) => {
      lines.push(`#### 焦点：${d.topic}`);
      lines.push(`- **市场一致预期**：${d.consensus || "广泛一致预期"}`);
      lines.push(`- **本次审慎推断**：${d.divergence}`);
      if (d.catalyst_trigger) lines.push(`- **核心观测/催化时间窗**：${d.catalyst_trigger}`);
      lines.push("");
    });
  }

  if (result.research_theses && result.research_theses.length > 0) {
    lines.push("## 二、核心研究论点与投资推演");
    lines.push("");
    result.research_theses.forEach((t, i) => {
      lines.push(`### ${i + 1}. ${t.title}`);
      if (t.detail) lines.push(t.detail);
      if (t.mechanism) lines.push(`- **传导机制**：${t.mechanism}`);
      if (t.conditions && t.conditions.length > 0) lines.push(`- **成立条件**：${t.conditions.join("；")}`);
      if (t.tracking_metrics && t.tracking_metrics.length > 0) lines.push(`- **跟踪指标**：${t.tracking_metrics.join("；")}`);
      if (t.invalidation) lines.push(`- **失效风险**：${t.invalidation}`);
      lines.push("");
    });
  }

  if (result.market_metrics && result.market_metrics.length > 0) {
    lines.push("## 三、市场规模与关键运行指标");
    lines.push("");
    lines.push("| 指标名称 | 数值/规模 | 统计期间 | 增速/趋势 |");
    lines.push("| --- | --- | --- | --- |");
    result.market_metrics.forEach((m) => {
      lines.push(`| **${m.label}** | ${m.value || "-"} | ${m.period || "-"} | ${m.growth || "-"} |`);
    });
    lines.push("");
  }

  if (result.technology_routes && result.technology_routes.length > 0) {
    lines.push("## 四、主流技术路线与演进壁垒");
    lines.push("");
    result.technology_routes.forEach((tr, i) => {
      lines.push(`### ${i + 1}. ${tr.title}`);
      if (tr.detail) lines.push(tr.detail);
      if (tr.evidence) lines.push(`> 依据：${tr.evidence}`);
      lines.push("");
    });
  }

  const stages = [
    { label: "上游", nodes: result.upstream },
    { label: "中游", nodes: result.midstream },
    { label: "下游", nodes: result.downstream },
  ];
  const hasNodes = stages.some((s) => s.nodes && s.nodes.length > 0);
  if (hasNodes) {
    lines.push("## 五、上下游环节与价值链分布");
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
    lines.push("## 六、产业链传导机制与核心假设");
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

  if (result.key_stocks && result.key_stocks.length > 0) {
    lines.push("## 七、核心龙头与重点关注标的");
    lines.push("");
    result.key_stocks.forEach((stock, i) => {
      const codeStr = stock.code ? ` (${stock.code})` : "";
      const valParts: string[] = [];
      if (stock.total_market_cap) valParts.push(`市值: ${stock.total_market_cap}`);
      if (stock.price_change) valParts.push(`现价: ${stock.price_change}`);
      if (stock.pe) {
        const peStr = stock.pe_percentile ? `PE: ${stock.pe} [${stock.pe_percentile}]` : `PE: ${stock.pe}`;
        valParts.push(peStr);
      }
      if (stock.pb) valParts.push(`PB: ${stock.pb}`);
      const valStr = valParts.length > 0 ? ` [${valParts.join(" | ")}]` : "";
      lines.push(`${i + 1}. **${stock.name || stock.company || stock.code}**${codeStr} - ${stock.role || "产业链核心企业"}${valStr}`);
      if (stock.benefit_path) {
        lines.push(`   - **受益路径**：${stock.benefit_path}`);
      }
      if (stock.consensus_forecast) {
        lines.push(`   - **机构一致预期**：${stock.consensus_forecast}`);
      }
      if (stock.gross_margin) {
        lines.push(`   - **毛利率**：${stock.gross_margin}`);
      }
      if (stock.overseas_share) {
        lines.push(`   - **海外出海占比**：${stock.overseas_share}`);
      }
      if (stock.roe || stock.growth_rate) {
        const perf = [stock.roe ? `ROE: ${stock.roe}` : "", stock.growth_rate ? `业绩增速: ${stock.growth_rate}` : ""].filter(Boolean);
        lines.push(`   - **资本回报与成长**：${perf.join(" ｜ ")}`);
      }
      if (stock.moat) {
        lines.push(`   - **竞争壁垒**：${stock.moat}`);
      }
      if (stock.eps_elasticity) {
        lines.push(`   - **业绩弹性**：${stock.eps_elasticity}`);
      }
      if (stock.restricted_risk) {
        lines.push(`   - **限售解禁监控**：${stock.restricted_risk}`);
      }
      if (stock.realization_conditions && stock.realization_conditions.length > 0) {
        lines.push(`   - **兑现条件**：${stock.realization_conditions.join("；")}`);
      }
    });
    lines.push("");
  }

  if (result.opportunities && result.opportunities.length > 0) {
    lines.push("## 八、投资机会与跟踪清单");
    lines.push("");
    lines.push("| 标的代码 | 标的名称 | 驱动逻辑与看点 | 资料完整度 |");
    lines.push("| --- | --- | --- | --- |");
    result.opportunities.forEach((op) => {
      const comp = op.completeness_score ?? (op as unknown as { completeness?: number }).completeness;
      lines.push(`| **${op.code || "-"}** | ${op.name} | ${op.rationale || "-"} | ${comp !== undefined ? `${comp}%` : "-"} |`);
    });
    lines.push("");
  }

  if (result.key_events && result.key_events.length > 0) {
    lines.push("## 九、关键产业催化事件");
    lines.push("");
    result.key_events.forEach((ev, i) => {
      lines.push(`### ${i + 1}. ${ev.title}${ev.date ? `（${ev.date}）` : ""}`);
      if (ev.impact) lines.push(`- **影响研判**：${ev.impact}`);
      lines.push("");
    });
  }

  if (result.risks && result.risks.length > 0) {
    lines.push("## 十、潜在风险与跟踪提示");
    lines.push("");
    result.risks.forEach((risk, i) => {
      lines.push(`${i + 1}. ${risk}`);
    });
    lines.push("");
  }

  return lines.join("\n");
}
