/**
 * README 界面配图抓取脚本（真实页面 + 真实后端数据）。
 *
 * 前置条件：
 *   1. 后端已运行在 http://127.0.0.1:8000（或通过 BACKEND_PORT 指定端口）；
 *   2. 前端 dev server 已运行在 http://127.0.0.1:4173（`npm run dev -- --port 4173`）；
 *   3. 存在可登录的管理员账号，密码通过环境变量传入：
 *        README_SHOT_USER=admin README_SHOT_PASSWORD=xxx node scripts/capture-readme-screenshots.mjs
 *
 * 输出：docs/images/<name>.png（1512×950，2x 渲染后按 CSS 尺寸输出，兼顾清晰度与体积）
 *
 * 该脚本不进 CI：它依赖真实后端与真实行情数据，只用于人工更新 README 配图。
 */
import { chromium } from "playwright";
import { mkdir } from "node:fs/promises";
import { dirname, resolve } from "node:path";
import { fileURLToPath } from "node:url";

const FRONTEND_URL = process.env.README_SHOT_FRONTEND ?? "http://127.0.0.1:4173";
const USERNAME = process.env.README_SHOT_USER ?? "admin";
const PASSWORD = process.env.README_SHOT_PASSWORD;
const OUT_DIR = resolve(dirname(fileURLToPath(import.meta.url)), "../../docs/images");

if (!PASSWORD) {
  console.error("缺少 README_SHOT_PASSWORD：请传入可登录账号的密码");
  process.exit(1);
}

/**
 * 需要抓取的页面：path → 输出名（顺序即 README 中展示顺序）。
 *
 * 只收录"离线/真实数据都能正常渲染"的页面：依赖 LLM Key 的对话、每日复盘、产业链
 * 报告页在没有配置模型时是空态，放进去会显得产品不可用，故不收录。
 * ``action`` 用于需要二次交互（切 Tab）才能看到代表性的页面。
 */
const PAGES = [
  { path: "/", name: "dashboard" },
  { path: "/market", name: "market" },
  { path: "/screener", name: "screener" },
  { path: "/portfolio", name: "portfolio" },
  { path: "/trading-calendar", name: "trading-calendar" },
  {
    path: "/quant",
    name: "quant",
    action: async (page) => {
      await page.getByRole("tab", { name: /结果分析/ }).click();
      await page.waitForTimeout(2500);
    },
  },
];

const browser = await chromium.launch();
const context = await browser.newContext({
  viewport: { width: 1512, height: 950 },
  deviceScaleFactor: 2,
  locale: "zh-CN",
  timezoneId: "Asia/Shanghai",
  colorScheme: "dark",
});
const page = await context.newPage();
const errors = [];
page.on("pageerror", (error) => errors.push(`pageerror: ${error.message}`));

await mkdir(OUT_DIR, { recursive: true });

// ── 登录页 ───────────────────────────────────────────────
await page.goto(`${FRONTEND_URL}/login`, { waitUntil: "networkidle" });
await page.waitForTimeout(800);
await page.screenshot({ path: resolve(OUT_DIR, "login.png") });
console.log("captured login.png");

// ── 真实登录 ─────────────────────────────────────────────
await page.fill("#username", USERNAME);
await page.fill("#login-password", PASSWORD);
await page.getByRole("button", { name: /登\s*录/ }).click();
await page.waitForURL((url) => !url.pathname.startsWith("/login"), { timeout: 30_000 });
await page.waitForLoadState("networkidle");

for (const target of PAGES) {
  await page.goto(`${FRONTEND_URL}${target.path}`, { waitUntil: "networkidle" });
  // 图表/动画/懒加载模块需要额外时间；同时等 body 不再是空壳。
  await page.waitForTimeout(3500);
  if (target.action) await target.action(page);
  // scale: "css" 让 2x 设备像素密度只用于清晰度，输出仍是 1512px 宽（README 体积可控）。
  await page.screenshot({ path: resolve(OUT_DIR, `${target.name}.png`), scale: "css" });
  console.log(`captured ${target.name}.png`);
}

await browser.close();

if (errors.length > 0) {
  console.warn("页面报错（可能影响配图质量）：");
  for (const error of errors) console.warn(`  ${error}`);
}
console.log(`输出目录：${OUT_DIR}`);
