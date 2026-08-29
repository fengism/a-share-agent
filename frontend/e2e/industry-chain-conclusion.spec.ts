import { expect, test, type Page } from "@playwright/test";

const user = {
  id: 7,
  username: "researcher",
  is_admin: false,
  must_change_password: false,
};

const result = {
  name: "AI算力",
  summary: "全球需求仍由云厂商资本开支驱动，价值量正从单卡向互连、散热和能源系统扩散。",
  positioning: "覆盖计算芯片、服务器、集群网络、液冷供电与算力运营。",
  aliases: ["AI基础设施"],
  market_metrics: [
    { label: "全球市场规模", value: "2050 亿美元", period: "2026E", growth: "+30%" },
    { label: "中国市场增速", value: "42%", period: "2026E" },
  ],
  upstream: [
    { name: "AI芯片", companies: ["海光信息"], role: "算力供给" },
  ],
  midstream: [
    { name: "服务器集成", companies: ["浪潮信息"], role: "系统交付" },
  ],
  downstream: [
    { name: "云计算", companies: ["云厂商"], role: "算力消纳" },
  ],
  drivers: [],
  driver_insights: [
    { title: "资本开支持续扩张", detail: "云厂商继续增加基础设施投入", confidence: "high" },
  ],
  trends: [
    { title: "机架级交付", detail: "整机向系统交付升级" },
    { title: "液冷渗透", detail: "高密度机柜加速液冷采用" },
    { title: "高速互连", detail: "集群规模提升网络价值量" },
    { title: "算电协同", detail: "能源系统成为扩容约束" },
  ],
  risks: [],
  risk_insights: [
    { title: "利用率不及预期", detail: "供需错配可能压低资产回报", confidence: "medium" },
  ],
  capital_moves: [],
  key_events: [],
  key_stocks: [
    { name: "浪潮信息", code: "000977", role: "服务器整机" },
  ],
  sources: [],
  llm_review: "# AI算力产业链分析\n\n## 结论\n\n完整研究正文。",
  charts: [],
  quality_status: "complete",
  archive_status: "saved",
  archive_id: "20260828_114423",
  research_scope: {
    region: "china_and_global",
    start_date: "2026-02-28",
    end_date: "2026-08-28",
    company_scope: "a_share",
  },
  coverage: {
    market: "complete",
    competition: "partial",
    technology: "partial",
    chain: "complete",
    companies: "complete",
    events: "partial",
  },
  missing_evidence: [],
  conflicts: [],
  evidence_catalog: [],
};

async function mockIndustryChainPage(page: Page) {
  await page.route(/^http:\/\/127\.0\.0\.1:4173\/api\//, async (route) => {
    const pathname = new URL(route.request().url()).pathname;
    let body: unknown = [];
    if (pathname === "/api/auth/me") body = user;
    else if (pathname === "/api/config") body = {};
    else if (pathname === "/api/workflows/active") body = [];
    else if (pathname === "/api/industry-chain/history") {
      body = [{
        name: "AI算力",
        archive_id: "20260828_114423",
        saved_at: "2026-08-28T11:44:23",
        title: "AI算力产业链研究",
        summary: result.summary,
        can_delete: true,
      }];
    } else if (pathname.includes("/api/industry-chain/AI%E7%AE%97%E5%8A%9B/archive/")) {
      body = result;
    } else if (pathname === "/api/industry-chain/atlas/chains") {
      body = { categories: [], chains: [], total_chains: 0, total_companies: 0 };
    }
    await route.fulfill({
      status: 200,
      contentType: "application/json",
      body: JSON.stringify(body),
    });
  });
}

test("keeps the industry conclusion decision-first and responsive", async ({ page }) => {
  await mockIndustryChainPage(page);
  await page.setViewportSize({ width: 1440, height: 1000 });
  await page.goto(`/industry-chain/${encodeURIComponent("AI算力")}`);
  await page.getByRole("button", { name: /^AI算力产业链研究/ }).click();

  const conclusion = page.getByRole("region", { name: "产业链结论摘要" });
  await expect(conclusion).toBeVisible();
  await expect(conclusion.getByText("核心判断")).toBeVisible();
  await expect(conclusion.getByText("核心驱动")).toBeVisible();
  await expect(conclusion.getByText("主要风险")).toBeVisible();
  await expect(conclusion.getByText("重点关注")).toBeVisible();
  await expect(page.getByRole("heading", { name: "详细分析" })).toBeVisible();
  await expect(page.getByRole("heading", { name: "研究依据" })).toBeVisible();
  const chapterNav = page.getByRole("navigation", { name: "报告章节导航" });
  await expect(chapterNav.getByRole("link")).toHaveCount(4);
  await expect(chapterNav.getByRole("link", { name: /01.*产业研判/ })).toHaveAttribute("href", "#industry-judgment");
  await expect(chapterNav.getByRole("link", { name: /04.*完整正文/ })).toHaveAttribute("href", "#industry-full-report");
  expect(await chapterNav.evaluate((element) => getComputedStyle(element).position)).toBe("sticky");
  await expect(page.getByRole("region", { name: "详细分析" }).locator(".ant-card")).toHaveCount(0);
  await expect(page.locator("details.industry-research-audit").first()).not.toHaveAttribute("open", "");
  await expect(page.locator("details.industry-research-more")).toHaveCount(0);
  await expect(page.getByText("算电协同")).toBeVisible();
  const desktopTiers = await page.locator(".industry-chain-tier").evaluateAll((elements) => (
    elements.map((element) => {
      const box = element.getBoundingClientRect();
      return { x: box.x, y: box.y };
    })
  ));
  expect(desktopTiers).toHaveLength(3);
  expect(Math.max(...desktopTiers.map((box) => box.y)) - Math.min(...desktopTiers.map((box) => box.y))).toBeLessThan(2);
  await expect(page.locator(".industry-report__full-report .ant-collapse-item")).not.toHaveClass(
    /ant-collapse-item-active/,
  );
  expect(await page.evaluate(() => document.documentElement.scrollWidth <= window.innerWidth + 1)).toBe(true);
  await page.screenshot({ path: "/tmp/industry-chain-conclusion-desktop.png", fullPage: true });

  await page.setViewportSize({ width: 390, height: 844 });
  await expect(conclusion).toBeVisible();
  expect(await chapterNav.evaluate((element) => element.scrollWidth > element.clientWidth)).toBe(true);
  const mobileTiers = await page.locator(".industry-chain-tier").evaluateAll((elements) => (
    elements.map((element) => {
      const box = element.getBoundingClientRect();
      return { x: box.x, y: box.y };
    })
  ));
  expect(mobileTiers).toHaveLength(3);
  expect(Math.max(...mobileTiers.map((box) => box.x)) - Math.min(...mobileTiers.map((box) => box.x))).toBeLessThan(2);
  expect(mobileTiers[0].y).toBeLessThan(mobileTiers[1].y);
  expect(mobileTiers[1].y).toBeLessThan(mobileTiers[2].y);
  expect(await page.evaluate(() => document.documentElement.scrollWidth <= window.innerWidth + 1)).toBe(true);
  await page.screenshot({ path: "/tmp/industry-chain-conclusion-mobile.png", fullPage: true });
});
