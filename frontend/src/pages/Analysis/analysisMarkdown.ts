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

  const rf = result.research_framework;
  if (rf) {
    if (rf.business_model || rf.moat) {
      lines.push("## 六、商业模式与核心护城河");
      lines.push("");
      if (rf.business_model?.economic_engine) {
        lines.push(`- **盈利引擎**：${rf.business_model.economic_engine}`);
      }
      if (rf.business_model?.earnings_quality) {
        lines.push(`- **盈利质量**：${rf.business_model.earnings_quality}`);
      }
      if (rf.moat?.overall_durability) {
        lines.push(`- **护城河持续性**：${rf.moat.overall_durability}`);
      }
      if (rf.moat?.moats && rf.moat.moats.length > 0) {
        lines.push("### 护城河明细与正反证");
        rf.moat.moats.forEach((m) => {
          lines.push(`- **${m.moat_type}**（强弱：${m.strength}，方向：${m.direction}）`);
          if (m.evidence?.length) lines.push(`  - 支持证据：${m.evidence.join("；")}`);
          if (m.counterevidence?.length) lines.push(`  - 反证/破坏因素：${m.counterevidence.join("；")}`);
        });
      }
      lines.push("");
    }

    if (rf.inversion) {
      lines.push("## 七、逆向思考与最强做空/下行逻辑 (Inversion)");
      lines.push("");
      if (rf.inversion.bear_case) {
        lines.push(`> **最强熊市观点**：${rf.inversion.bear_case}`);
        lines.push("");
      }
      if (rf.inversion.risks && rf.inversion.risks.length > 0) {
        lines.push("### 失败路径与下行风险");
        rf.inversion.risks.forEach((r, idx) => {
          lines.push(`${idx + 1}. **${r.risk}**（概率：${r.probability}，冲击：${r.impact}）`);
          if (r.failure_path) lines.push(`   - 失败演化路径：${r.failure_path}`);
          if (r.leading_indicators?.length) lines.push(`   - 领先先行指标：${r.leading_indicators.join("、")}`);
        });
        lines.push("");
      }
    }

    if (rf.actions) {
      lines.push("## 八、条件化投资决策与失效跟踪");
      lines.push("");
      lines.push(`- **新投资者建议**：${rf.actions.new_investor_action}`);
      lines.push(`- **已持有者建议**：${rf.actions.holder_action}`);
      if (rf.actions.rationale) lines.push(`- **决策依据**：${rf.actions.rationale}`);
      if (rf.actions.buy_or_add_range) {
        lines.push(`- **参考买入/加仓区间**：¥${rf.actions.buy_or_add_range[0]} - ¥${rf.actions.buy_or_add_range[1]}`);
      }
      if (rf.actions.thesis_breakers && rf.actions.thesis_breakers.length > 0) {
        lines.push("### 核心投资逻辑失效条件 (Thesis Breakers)");
        rf.actions.thesis_breakers.forEach((tb) => lines.push(`- ⚠️ ${tb}`));
      }
      if (rf.actions.monitoring_metrics && rf.actions.monitoring_metrics.length > 0) {
        lines.push("### 持续跟踪指标");
        rf.actions.monitoring_metrics.forEach((mm) => lines.push(`- 🔍 ${mm}`));
      }
      lines.push("");
    }
  }

  return lines.join("\n");
}
