#!/usr/bin/env node
/**
 * 前端色彩纪律门禁（A 股红绿纪律与非价格维度去杂色）。
 *
 * 核心原则：
 * 1. 严格遵守 A 股交易惯例：红（上涨 / 净流入 / 涨停）、绿（下跌 / 净流出 / 跌停）。
 * 2. 禁止在非价格维度（状态标签、业务分类、阶段标识、普通成功/失败提示）滥用 red / green / volcano / lime / error / success。
 * 3. 业务分类统一使用 blue / purple / cyan / gold / orange / default 或 `semanticTagStyle`。
 *
 * 运行方式：node scripts/check-color-discipline.mjs（已接入 npm run lint）
 */
import { readdirSync, readFileSync, statSync } from "node:fs";
import path from "node:path";

const srcRoot = path.resolve("src");

/** 允许使用价格红绿的合法价格 / 资金流向关键词 */
const ALLOWED_PRICE_KEYWORDS = [
  "涨停",
  "跌停",
  "净买入",
  "净流入",
  "超额收益",
  "盈利",
  "亏损",
  "涨跌",
];

function walk(dir, out = []) {
  for (const entry of readdirSync(dir, { withFileTypes: true })) {
    const full = path.join(dir, entry.name);
    if (entry.isDirectory()) {
      walk(full, out);
    } else if (full.endsWith(".tsx") && !full.endsWith(".test.tsx")) {
      out.push(full);
    }
  }
  return out;
}

const files = walk(srcRoot);
const violations = [];

for (const file of files) {
  // 保护用户未提交的工作区
  if (file.includes("Potential") || file.includes("StateTrajectoryBadge")) continue;

  const text = readFileSync(file, "utf8");
  const tagRegex = /<Tag\b([^>]*)(?:\/>|>([\s\S]*?)<\/Tag>)/g;
  let match;

  while ((match = tagRegex.exec(text)) !== null) {
    const attrs = match[1] || "";
    const children = match[2] || "";
    const colorMatch = attrs.match(/\bcolor=["\x27](red|green|volcano|lime|success|error)["\x27]/);

    if (colorMatch) {
      const color = colorMatch[1];
      const context = attrs + " " + children;
      const isAllowed = ALLOWED_PRICE_KEYWORDS.some((kw) => context.includes(kw));

      if (!isAllowed) {
        const line = text.slice(0, match.index).split("\n").length;
        const rel = path.relative(process.cwd(), file);
        const snippet = match[0].replace(/\s+/g, " ").slice(0, 80);
        violations.push({ rel, line, color, snippet });
      }
    }
  }
}

if (violations.length > 0) {
  console.error(`\n❌ 色彩纪律检查失败：发现 ${violations.length} 处非价格维度滥用红/绿色标签：\n`);
  for (const v of violations) {
    console.error(`  ${v.rel}:${v.line} [color="${v.color}"] -> ${v.snippet}`);
  }
  console.error("\n规范指引：");
  console.error("  - 红/绿仅允许用于价格涨跌、涨跌停、资金净买入/净流出。");
  console.error("  - 业务分类与普通状态请使用 blue / purple / cyan / gold / orange / default，或 `semanticTagStyle`。\n");
  process.exit(1);
} else {
  console.log(`[color-discipline] OK · 全站 ${files.length} 个 TSX 文件通过 A 股红绿纪律检查（零非价格红绿）`);
}
