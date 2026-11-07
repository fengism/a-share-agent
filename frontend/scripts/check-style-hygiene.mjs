#!/usr/bin/env node
/**
 * 样式卫生门禁（棘轮机制）。
 *
 * 前端历史遗留了大量内联样式 `style={{ ... }}` 与 CSS `!important`，二者是
 * 视觉杂乱与样式互相污染的主要来源。全量清理周期较长，因此先设「总量预算」：
 * 只允许数量下降，不允许新代码把总量推高。
 *
 * 清理掉一批后，请同步下调下面的预算常量，让棘轮继续收紧。
 *
 * 运行方式：node scripts/check-style-hygiene.mjs（已挂在 npm run lint 上）
 */
import { readdirSync, readFileSync } from "node:fs";
import path from "node:path";

const srcRoot = path.resolve("src");

/** 当前基线。只允许下调，不允许上调。 */
// 实际 1783，预留 20 处缓冲，避免正常功能开发被门禁直接卡死；下轮清理后同步下调。
const INLINE_STYLE_BUDGET = 1803;
const IMPORTANT_BUDGET = 177;

/**
 * 单个 CSS 文件行数上限。
 *
 * 原 2637 行的 `base.css` 已拆到 `src/styles/base/`，1873 行的 `national-team.css`
 * 与 1872 行的 `industry-report.css` 已拆到各自页面的 `styles/` 目录。巨型样式单文件
 * 一旦重现就会退回“找不到规则、只能加 !important”的老路，所以设这道上限兜底。
 *
 * 当前最大为 `app-header.css` 的 381 行，距上限 394 有 13 行余量；
 * `app-shell-chrome.css` 与 `portfolio.css` 已各拆为两个分片。继续拆分大文件后请同步下调此值。
 */
const MAX_CSS_LINES = 394;

/** 单个文件最多报告的语法问题条数，避免刷屏 */
const MAX_REPORTED_ISSUES = 10;

function walk(dir, out = []) {
  for (const entry of readdirSync(dir, { withFileTypes: true })) {
    const full = path.join(dir, entry.name);
    if (entry.isDirectory()) {
      walk(full, out);
    } else {
      out.push(full);
    }
  }
  return out;
}

function countMatches(text, pattern) {
  return (text.match(pattern) || []).length;
}

/**
 * CSS 结构体检（零依赖，不引 postcss）。
 *
 * 背景：`feed.css` 曾残留一段改坏的编辑——`.feed-analysis-text` 已经闭合，后面又跟了
 * 一行 `line-height: ...;` 和孤立的 `}`。浏览器会静默跳过，所以一直没人发现；但它让
 * postcss / 压缩器 / 任何 `@import` 直接报 `Unexpected }`，也是那个文件无法被拆分的
 * 真实原因。**构建不报错不代表 CSS 合法**，因此在这里做机械检查。
 *
 * 判定只依据「顶层语句边界」，不猜测属性名，避免把 `::before` / `:hover` /
 * `.ant-tabs-nav:` 这类选择器误判成裸声明：
 *   - 顶层遇到 `}` 时前面积为空  → 多余的 `}`
 *   - 顶层选择器前含 `;`         → 裸声明或孤立分号混进了选择器
 *   - 文件结束时仍有未闭合的 `{`  → 缺 `}`
 *   - 文件结束时仍残留前面积      → 末尾有多余内容
 */
function findCssSyntaxIssues(text) {
  const issues = [];
  let depth = 0;
  let line = 1;
  let prelude = "";
  let preludeLine = 1;

  const push = (msg) => {
    if (issues.length < MAX_REPORTED_ISSUES) issues.push(msg);
  };

  let i = 0;
  while (i < text.length) {
    const ch = text[i];

    if (ch === "\n") {
      line++;
      if (depth === 0 && prelude.trim() === "") preludeLine = line + 1;
      i++;
      continue;
    }

    if (ch === "/" && text[i + 1] === "*") {
      const end = text.indexOf("*/", i + 2);
      if (end === -1) {
        push(`第 ${line} 行：注释未闭合`);
        return issues;
      }
      line += (text.slice(i, end).match(/\n/g) || []).length;
      i = end + 2;
      continue;
    }

    if (ch === '"' || ch === "'") {
      const quote = ch;
      let j = i + 1;
      while (j < text.length && text[j] !== quote) {
        if (text[j] === "\\") j++;
        j++;
      }
      if (j >= text.length) {
        push(`第 ${line} 行：字符串未闭合`);
        return issues;
      }
      line += (text.slice(i, j).match(/\n/g) || []).length;
      // 字符串内容不进前面积：属性选择器里的 ; 不算非法
      if (depth === 0) prelude += '""';
      i = j + 1;
      continue;
    }

    if (ch === "{") {
      if (depth === 0) {
        if (prelude.trim() === "") {
          push(`第 ${line} 行：\`{\` 之前没有选择器`);
          return issues;
        }
        if (prelude.includes(";") && !prelude.trim().startsWith("@")) {
          push(
            `第 ${preludeLine} 行：选择器前出现了 \`;\` —— 说明有裸声明或孤立分号混在规则之外`,
          );
          return issues;
        }
      }
      depth++;
      prelude = "";
      i++;
      continue;
    }

    if (ch === "}") {
      if (depth === 0) {
        push(
          `第 ${line} 行：多余的 \`}\` —— 此处没有未闭合的块` +
            `（浏览器会静默跳过，postcss 会报 Unexpected }）`,
        );
        return issues;
      }
      depth--;
      prelude = "";
      preludeLine = line;
      i++;
      continue;
    }

    if (ch === ";") {
      if (depth === 0) {
        if (!prelude.trim().startsWith("@")) {
          push(
            `第 ${line} 行：规则之外出现孤立的 \`;\` —— 通常是改坏了的编辑，` +
              `声明落在了规则外面（浏览器静默跳过，postcss 报 Unexpected }）`,
          );
          return issues;
        }
        prelude = "";
      }
      i++;
      continue;
    }

    if (depth === 0) {
      if (prelude.trim() === "") preludeLine = line;
      prelude += ch;
    }
    i++;
  }

  if (depth > 0) {
    push(`文件末尾仍有 ${depth} 个未闭合的 \`{\``);
  } else if (prelude.trim() !== "") {
    push(`第 ${preludeLine} 行：文件末尾残留不属于任何规则的内容`);
  }
  return issues;
}

const files = walk(srcRoot);
const inlineByFile = [];
const importantByFile = [];
const oversizedCss = [];
const cssSyntaxIssues = [];
let inlineTotal = 0;
let importantTotal = 0;

for (const file of files) {
  const rel = path.relative(process.cwd(), file);
  if (file.endsWith(".tsx") && !file.endsWith(".test.tsx")) {
    const n = countMatches(readFileSync(file, "utf8"), /style=\{\{/g);
    if (n > 0) {
      inlineTotal += n;
      inlineByFile.push([n, rel]);
    }
  } else if (file.endsWith(".css")) {
    const text = readFileSync(file, "utf8");
    const n = countMatches(text, /!important/g);
    if (n > 0) {
      importantTotal += n;
      importantByFile.push([n, rel]);
    }
    const lineCount = text.split("\n").length - 1;
    if (lineCount > MAX_CSS_LINES) {
      oversizedCss.push([lineCount, rel]);
    }
    for (const issue of findCssSyntaxIssues(text)) {
      cssSyntaxIssues.push(`${rel}: ${issue}`);
    }
  }
}

function top(entries, limit = 8) {
  return entries
    .sort((a, b) => b[0] - a[0])
    .slice(0, limit)
    .map(([n, rel]) => `  ${String(n).padStart(4)}  ${rel}`)
    .join("\n");
}

const inlineOver = inlineTotal > INLINE_STYLE_BUDGET;
const importantOver = importantTotal > IMPORTANT_BUDGET;
const cssSizeOver = oversizedCss.length > 0;
const cssSyntaxBroken = cssSyntaxIssues.length > 0;

if (inlineOver || importantOver || cssSizeOver || cssSyntaxBroken) {
  console.error("[style-hygiene] 样式预算超支：");
  if (inlineOver) {
    console.error(`  内联样式 ${inlineTotal} > ${INLINE_STYLE_BUDGET}，请优先收敛以下文件：`);
    console.error(top(inlineByFile));
  }
  if (importantOver) {
    console.error(`  !important ${importantTotal} > ${IMPORTANT_BUDGET}，请优先收敛以下文件：`);
    console.error(top(importantByFile));
  }
  if (cssSizeOver) {
    console.error(`  单个 CSS 文件超过 ${MAX_CSS_LINES} 行，请按关注点拆分：`);
    console.error(top(oversizedCss));
  }
  if (cssSyntaxBroken) {
    console.error("  CSS 结构不合法（浏览器会静默跳过，但 postcss/压缩器/拆分都会失败）：");
    for (const issue of cssSyntaxIssues) console.error(`    ${issue}`);
  }
  console.error(
    "提示：把重复的内联样式抽成页面 CSS 类（优先复用 --c-* 变量），不要在既有预算上继续加码。",
  );
  process.exit(1);
}

const savedInline = INLINE_STYLE_BUDGET - inlineTotal;
const savedImportant = IMPORTANT_BUDGET - importantTotal;
console.log(
  `[style-hygiene] OK · inline ${inlineTotal}/${INLINE_STYLE_BUDGET}（余量 ${savedInline}）` +
    ` · !important ${importantTotal}/${IMPORTANT_BUDGET}（余量 ${savedImportant}）` +
    ` · CSS 结构检查 ${files.filter((f) => f.endsWith(".css")).length} 个文件通过`,
);
