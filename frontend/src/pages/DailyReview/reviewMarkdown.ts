/**
 * 每日复盘 → Markdown 导出。
 *
 * 从页面组件里独立出来：可单独测试，也不会因为页面布局调整而顺带改动导出格式。
 * 章节顺序与页面（Hero → 图谱 → 政策 → … → 报告）保持一致，便于"看到的"和"导出的"对得上。
 */

import type { DailyReviewResult } from "../../types/dailyReview";
import { buildMoodSummary, formatSignedPct } from "./reviewView";

/** 去掉 ```json 围栏，返回可解析的正文 */
export function unwrapJsonBlock(value: string): string {
  const text = value.trim();
  const match = text.match(/^```(?:json)?\s*([\s\S]*?)\s*```$/i);
  return match ? match[1].trim() : text;
}

/** 把任意复盘字段值铺平成 Markdown 列表 */
export function stringifyReviewValue(value: unknown, depth = 0): string {
  if (value == null) return "";
  if (typeof value === "string") {
    return value.replace(/\\n/g, "\n").trim();
  }
  if (Array.isArray(value)) {
    return value
      .map((item) => {
        if (typeof item === "string") {
          return `- ${item.replace(/\\n/g, "\n").trim()}`;
        }
        return `- ${stringifyReviewValue(item, depth + 1)}`;
      })
      .join("\n");
  }
  if (typeof value === "object") {
    return Object.entries(value as Record<string, unknown>)
      .map(([key, item]) => {
        if (typeof item === "string") {
          const itemText = item.replace(/\\n/g, "\n").trim();
          if (itemText.includes("\n")) {
            const lines = itemText.split("\n").map((line) => line.trim()).filter(Boolean);
            return `- **${key}**：\n${lines.map((line) => `  - ${line}`).join("\n")}`;
          }
          return `- **${key}**：${itemText}`;
        }
        return `- **${key}**：\n${stringifyReviewValue(item, depth + 1)}`;
      })
      .join("\n");
  }
  return String(value);
}

export function formatReviewTitle(key: string): string {
  return key
    .replace(/_/g, " ")
    .replace(/([a-z])([A-Z])/g, "$1 $2")
    .replace(/^./, (char) => char.toUpperCase());
}

/** 渲染深度复盘正文：JSON 会转成分节 Markdown，普通文本原样返回 */
export function renderReviewContent(value: string): string {
  if (!value) return "";
  const text = unwrapJsonBlock(value);
  try {
    const parsed = JSON.parse(text) as unknown;
    if (parsed && typeof parsed === "object" && !Array.isArray(parsed)) {
      return Object.entries(parsed as Record<string, unknown>)
        .map(([key, item]) => `## ${formatReviewTitle(key)}\n\n${stringifyReviewValue(item)}`)
        .join("\n\n");
    }
    return stringifyReviewValue(parsed);
  } catch {
    return text.replace(/\\n/g, "\n");
  }
}

export function buildDailyReviewMarkdown(review: DailyReviewResult): string {
  const parts: string[] = [];
  parts.push(`# ${review.title}`);
  parts.push(`> **复盘日期**：${review.date} | **生成时间**：${review.generated_at || "-"} | **质量状态**：${review.quality_status === "degraded" ? "降级" : "完整"}\n`);
  parts.push(`## 市场总览\n\n${review.market_summary}\n`);
  parts.push(`## 市场情绪结论\n\n${buildMoodSummary(review)}\n`);

  if (review.llm_review) {
    parts.push(`## 深度复盘报告\n\n${renderReviewContent(review.llm_review)}\n`);
  } else {
    for (const section of [
      review.index_review,
      review.hotspot_review,
      review.dragon_tiger_review,
      review.news_policy_review,
    ]) {
      if (section?.title) {
        parts.push(`## ${section.title}\n\n${section.summary || ""}\n`);
        if (section.bullets?.length) {
          parts.push(section.bullets.map((b) => `- ${b}`).join("\n"));
        }
        parts.push("\n");
      }
    }
  }

  if (review.opportunities?.length || review.risk_alerts?.length || review.strategy_notes?.length) {
    parts.push("## 机会与风险展望\n");
    if (review.opportunities?.length) {
      parts.push(`- **机会**：${review.opportunities.join("；")}`);
    }
    if (review.risk_alerts?.length) {
      parts.push(`- **风险**：${review.risk_alerts.join("；")}`);
    }
    if (review.strategy_notes?.length) {
      parts.push(`- **策略建议**：${review.strategy_notes.join("；")}`);
    }
    parts.push("");
  }

  if (review.sentiment_cycle) {
    parts.push(`## 情绪周期定位：${review.sentiment_cycle.stage}\n`);
    if (review.sentiment_cycle.ladder_health) {
      parts.push(`- 梯队健康度：${review.sentiment_cycle.ladder_health}`);
    }
    for (const item of review.sentiment_cycle.evidence ?? []) {
      parts.push(`- 依据：${item}`);
    }
    parts.push("");
  }

  if (review.scenario_plans?.length) {
    parts.push("## 明日三情景预案\n");
    for (const scenario of review.scenario_plans) {
      parts.push(`- **${scenario.name}**：触发 ${scenario.trigger || "待补充"}；应对 ${scenario.playbook || "待补充"}`);
      if (scenario.watch_levels?.length) {
        parts.push(`  - 观察信号：${scenario.watch_levels.join("；")}`);
      }
    }
    parts.push("");
  }

  if (review.next_day_watchlist?.length) {
    parts.push("## 次日观察锚点\n");
    parts.push(
      review.next_day_watchlist
        .map((item) => `- **${item.name}**（${item.role}）：${item.reason || "待补充"}；触发 ${item.trigger || "待补充"}`)
        .join("\n"),
    );
    parts.push("");
  }

  if (review.key_levels?.length) {
    parts.push("## 关键点位与量能阈值\n");
    parts.push(review.key_levels.map((item) => `- ${item}`).join("\n"));
    parts.push("");
  }

  const check = review.previous_review_check;
  if (check) {
    parts.push(`## 上一交易日复盘自检（${check.review_date} → ${check.verified_date}）\n`);
    if (check.previous_stage) {
      parts.push(`- 上一交易日周期定位：${check.previous_stage}`);
    }
    if (check.previous_limit_up_count != null && check.limit_up_count != null) {
      parts.push(`- 涨停家数：${check.previous_limit_up_count} → ${check.limit_up_count}`);
    }
    for (const index of check.indices ?? []) {
      if (index.change_pct == null && index.previous_change_pct == null) {
        continue;
      }
      parts.push(`- ${index.name}：${formatSignedPct(index.previous_change_pct)} → ${formatSignedPct(index.change_pct)}`);
    }
    for (const item of check.watchlist ?? []) {
      if (item.missing) {
        parts.push(`- ${item.name}：次日行情缺失`);
        continue;
      }
      const limitUp = item.limit_up ? "，次日涨停" : "";
      parts.push(`- ${item.name}：次日 ${formatSignedPct(item.change_pct)}${limitUp}（${item.hit ? "命中" : "落空"}）`);
    }
    if (check.checked_count) {
      parts.push(`- 观察标的命中率：${check.hit_count}/${check.checked_count}`);
    }
    if (check.note) {
      parts.push(`- 说明：${check.note}`);
    }
    parts.push("");
  }

  const trend = review.cycle_trend;
  if (trend?.points?.length) {
    parts.push("## 情绪周期历史趋势\n");
    for (const point of trend.points.slice(-10)) {
      const bits = [point.date, point.stage || "未定位"];
      if (point.limit_up_count != null) {
        bits.push(`涨停 ${point.limit_up_count} 家`);
      }
      if (point.break_rate != null) {
        bits.push(`炸板率 ${(point.break_rate * 100).toFixed(1)}%`);
      }
      if (point.index_change_pct != null) {
        bits.push(`指数 ${formatSignedPct(point.index_change_pct)}`);
      }
      if (point.next_index_change_pct != null) {
        bits.push(`次日指数 ${formatSignedPct(point.next_index_change_pct)}`);
      }
      if (point.stage_transition) {
        bits.push(point.stage_transition);
      }
      parts.push(`- ${bits.join("；")}`);
    }
    for (const stat of trend.stage_stats ?? []) {
      parts.push(`- 阶段统计：${stat.stage} 出现 ${stat.occurrences} 次`);
    }
    if (trend.note) {
      parts.push(`- 说明：${trend.note}`);
    }
    parts.push("");
  }

  const sourceStatus = review.data_snapshot?.source_status;
  if (sourceStatus && Object.keys(sourceStatus).length) {
    parts.push("## 复盘数据状态\n");
    parts.push(
      Object.entries(sourceStatus)
        .map(([name, status]) => {
          const label = status.status === "complete" ? "完整" : status.status === "partial" ? "部分" : "不可用";
          const dataDate = status.data_date ? `（数据日期 ${status.data_date}）` : "";
          const error = status.error ? ` — ${status.error}` : "";
          return `- ${name}：${label}${dataDate}${error}`;
        })
        .join("\n"),
    );
    parts.push("");
  }

  if (review.warnings?.length) {
    parts.push("## 数据核验警告\n");
    parts.push(review.warnings.map((warning) => `- ⚠️ ${warning}`).join("\n"));
    parts.push("");
  }

  if (review.notes?.length) {
    parts.push("## 数据说明\n");
    parts.push(review.notes.map((note) => `- ${note}`).join("\n"));
    parts.push("");
  }

  return parts.join("\n");
}
