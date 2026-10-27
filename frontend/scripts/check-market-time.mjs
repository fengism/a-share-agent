#!/usr/bin/env node
/**
 * 时区门禁：后端时间戳是「北京时间墙上时钟 + 无时区后缀」，前端必须经由
 * `src/utils/marketTime.ts` 解析与渲染。否则浏览器按本地时区解释，非 UTC+8
 * 用户看到的行情时间会整体偏移（纯日期串还会差一天）。
 *
 * 规则：
 * 1. 禁止直接 `new Date(非空参数)`（`new Date()` 表示当前时刻，放行）；
 * 2. 带日期字段的 `toLocale*String()` 必须显式传 `timeZone`；
 * 3. 禁止 `toISOString()`：它输出 UTC 日期，做文件名/默认日期会在北京时间
 *    00:00–08:00 之间差一天，请改用 `marketDateStamp()`。
 *
 * 说明：单纯展示墙上时钟（`dayjs(naive).format(...)`、直接把后端字符串塞进 JSX）
 * 不会被这条门禁拦——它输出的就是北京时间原文。真正需要收口的是
 * 「拿北京时间串去和真实时刻比较/换算」（相对时间、`.diff()`、epoch 渲染）。
 *
 * 运行方式：node scripts/check-market-time.mjs（已挂在 npm run lint 上）
 */
import { readdirSync, readFileSync, statSync } from "node:fs";
import path from "node:path";

const srcRoot = path.resolve("src");

/**
 * 允许直接构造 Date 的文件：
 * - utils/marketTime.ts：收口实现本身
 * - utils/tradingSession.ts：只用 epoch 做日期加减，格式化仍锁 Asia/Shanghai
 * - charts/IntradayChart.tsx / charts/intradayTimeRange.ts：分时图把时间戳当
 *   「市场墙上时钟」用 getUTC* 直接上轴，内部自洽
 */
const DATE_CONSTRUCTION_ALLOWLIST = new Set([
  "utils/marketTime.ts",
  "utils/tradingSession.ts",
  "charts/IntradayChart.tsx",
  "charts/intradayTimeRange.ts",
]);

/** 允许出现「未指定 timeZone 的日期式 toLocale*String」的文件（当前为空）。 */
const LOCALE_FORMAT_ALLOWLIST = new Set([]);

/** 允许调用 `toISOString()` 的文件（当前为空：日期戳统一用 marketDateStamp）。 */
const UTC_SERIALIZE_ALLOWLIST = new Set([]);

const SOURCE_FILE = /\.(ts|tsx)$/;
const TEST_FILE = /\.(test|spec)\.(ts|tsx)$/;
const DATE_FIELD =
  /\b(year|month|day|hour|minute|second|hour12|hourCycle|dateStyle|timeStyle|timeZone)\b/;
const LOCALE_DATE_CALL = /\.toLocale(String|DateString|TimeString)\(/g;

const sourceFiles = [];

function collectSourceFiles(directory) {
  for (const entry of readdirSync(directory)) {
    if (entry === "node_modules" || entry.startsWith(".")) continue;
    const entryPath = path.join(directory, entry);
    if (statSync(entryPath).isDirectory()) {
      collectSourceFiles(entryPath);
    } else if (SOURCE_FILE.test(entry) && !TEST_FILE.test(entry)) {
      sourceFiles.push(entryPath);
    }
  }
}

collectSourceFiles(srcRoot);

function relative(file) {
  return path.relative(srcRoot, file).split(path.sep).join("/");
}

function lineOf(source, index) {
  return source.slice(0, index).split("\n").length;
}

/** 取出从 `(` 开始到配对的 `)` 结束的调用参数片段。 */
function callArguments(source, openIndex) {
  let depth = 0;
  for (let index = openIndex; index < source.length; index += 1) {
    const char = source[index];
    if (char === "(") depth += 1;
    else if (char === ")") {
      depth -= 1;
      if (depth === 0) return source.slice(openIndex + 1, index);
    }
  }
  return "";
}

const violations = [];

for (const file of sourceFiles) {
  const name = relative(file);
  const source = readFileSync(file, "utf8");

  if (!DATE_CONSTRUCTION_ALLOWLIST.has(name)) {
    for (const match of source.matchAll(/new Date\(/g)) {
      const args = callArguments(source, match.index + "new Date".length).trim();
      if (args === "") continue;
      violations.push(
        `${name}:${lineOf(source, match.index)} 直接 new Date(${args.slice(0, 60)})，请改用 utils/marketTime`,
      );
    }
  }

  if (!UTC_SERIALIZE_ALLOWLIST.has(name)) {
    for (const match of source.matchAll(/\.toISOString\(/g)) {
      violations.push(
        `${name}:${lineOf(source, match.index)} toISOString() 输出 UTC 日期，请改用 marketDateStamp/formatMarket*`,
      );
    }
  }

  if (!LOCALE_FORMAT_ALLOWLIST.has(name)) {
    for (const match of source.matchAll(LOCALE_DATE_CALL)) {
      const args = callArguments(source, match.index + match[0].length - 1);
      // 数字千分位（toLocaleString("zh-CN", { maximumFractionDigits })）不含日期字段
      if (!DATE_FIELD.test(args)) continue;
      if (/\btimeZone\s*:/.test(args)) continue;
      violations.push(
        `${name}:${lineOf(source, match.index)} ${match[0]} 缺 timeZone，请改用 utils/marketTime`,
      );
    }
  }
}

if (violations.length > 0) {
  console.error("时间戳展示必须走 utils/marketTime 收口，发现以下违规：");
  for (const violation of violations) console.error(`  ${violation}`);
  process.exit(1);
}

console.log(`market-time check passed (${sourceFiles.length} files)`);
