import type { AnalysisResult } from "../../types/stock";
import type { StockBasicInfo } from "../../types/stock/profile";

export function buildAnalysisMarkdown(
  result: AnalysisResult,
  info?: StockBasicInfo | null,
): string {
  const lines: string[] = [];
  const name = result.stock_name || info?.name || result.stock_code || "个股研报";
  const code = result.stock_code || info?.code || "";
  lines.push(`# ${name} (${code}) 深度投研分析报告`);
  lines.push("");
  if (result.analysis_date) {
    lines.push(`> 分析日期：${result.analysis_date}`);
  }
  if (result.current_price) {
    lines.push(`> 最新价格：¥${result.current_price.toFixed(2)}`);
  }
  lines.push("");

  lines.push("## 一、核心投资评级与结论");
  lines.push("");
  if (result.overall_rating != null) {
    lines.push(`- **综合评分**：${result.overall_rating} / 10`);
  }
  if (result.signal) {
    lines.push(`- **操作信号**：${result.signal}`);
  }
  if (result.confidence != null) {
    lines.push(`- **置信度**：${(result.confidence * 100).toFixed(0)}%`);
  }
  if (result.overall_summary) {
    lines.push("");
    lines.push("### 投资摘要");
    lines.push(result.overall_summary);
  }
  lines.push("");

  if (result.key_factors && result.key_factors.length > 0) {
    lines.push("## 二、核心驱动因素");
    lines.push("");
    result.key_factors.forEach((factor, idx) => {
      lines.push(`${idx + 1}. ${factor}`);
    });
    lines.push("");
  }

  if (result.risk_warnings && result.risk_warnings.length > 0) {
    lines.push("## 三、主要风险提示");
    lines.push("");
    result.risk_warnings.forEach((risk, idx) => {
      lines.push(`${idx + 1}. ${risk}`);
    });
    lines.push("");
  }

  if (result.fair_value_range || result.estimated_price_range || result.valuation_view) {
    lines.push("## 四、估值分析与目标区间");
    lines.push("");
    if (result.fair_value_range) {
      lines.push(`- **公允价值区间**：¥${result.fair_value_range[0]} - ¥${result.fair_value_range[1]}`);
    }
    if (result.estimated_price_range) {
      lines.push(`- **目标价格区间**：¥${result.estimated_price_range[0]} - ¥${result.estimated_price_range[1]}`);
    }
    if (result.valuation_view) {
      lines.push(`- **估值观点**：${result.valuation_view}`);
    }
    lines.push("");
  }

  if (result.technical) {
    lines.push("## 五、技术面与关键点位");
    lines.push("");
    if (result.technical.support_level) lines.push(`- **支撑位**：¥${result.technical.support_level}`);
    if (result.technical.resistance_level) lines.push(`- **阻力位**：¥${result.technical.resistance_level}`);
    if (result.technical.trend) lines.push(`- **趋势判断**：${result.technical.trend}`);
    if (result.technical.summary) lines.push(`- **技术面综述**：${result.technical.summary}`);
    lines.push("");
  }

  return lines.join("\n");
}
