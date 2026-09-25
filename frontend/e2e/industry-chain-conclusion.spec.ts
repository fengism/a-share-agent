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

test("shows evidence boundaries, business conditions and refresh controls", async ({ page }) => {
  await mockIndustryChainPage(page);
  await page.route(/\/api\/industry-chain\/.*\/archive\//, async route => {
    await route.fulfill({ json: {
      ...result,
      key_stocks: [{ name: "示例公司", code: "000001", role: "服务器集成", business_relevance: "concept", benefit_path: "订单交付转化收入", realization_conditions: ["验收完成"], invalidation_conditions: ["订单取消"], tracking_metrics: ["交付数量"] }],
      opportunities: [{ name: "示例公司", scoring_version: 2, score_kind: "research_completeness", completeness_score: 75, total_score: 75 }],
      changes: { previous_archive_id: "old", comparable: false, comparison_note: "研究区域不同", has_changes: false, items: [] },
      relationships: [{ title: "成本传导", source_node: "AI芯片", target_node: "服务器集成", relation_type: "transmission", impact_direction: "negative", detail: "成本上涨可能压缩整机利润", conditions: ["售价无法同步上涨"], invalidation: "客户接受调价", evidence_ids: [] }],
    } });
  });
  await page.goto(`/industry-chain/${encodeURIComponent("AI算力")}`);
  await page.getByRole("button", { name: /^AI算力产业链研究/ }).click();
  await expect(page.getByText("资料完整度 75%")).toBeVisible();
  await expect(page.getByText("盈利、估值、景气：未评估")).toBeVisible();
  await expect(page.getByText("研究区域不同")).toBeVisible();
  await expect(page.getByText("AI芯片 → 服务器集成")).toBeVisible();
  await expect(page.getByText("订单取消", { exact: true })).toBeVisible();
  await page.getByRole("button", { name: "关键结论核验 · 原文匹配不等于事实核实" }).click();
  await expect(page.getByText("待验证", { exact: true }).first()).toBeVisible();
  await page.getByRole("radio", { name: "只看原文匹配" }).check();
  await expect(page.getByText("当前筛选下没有结论")).toBeVisible();
  await page.getByRole("radio", { name: "只看待验证" }).check();
  await expect(page.getByText("待验证", { exact: true }).first()).toBeVisible();
  await page.getByText("分析范围（可选）").click();
  const refresh = page.getByRole("combobox", { name: "刷新公共数据维度" });
  await expect(refresh).toBeVisible();
  await refresh.click();
  await page.locator(".ant-select-item-option-content").getByText("事件", { exact: true }).click();
  await refresh.press("Escape");
  await expect(page.locator(".ant-select-dropdown:visible")).toHaveCount(0);
  let submitted: Record<string, unknown> | undefined;
  await page.route(/\/api\/workflows\/industry-chain\//, async route => {
    submitted = route.request().postDataJSON();
    await route.fulfill({ status: 503, json: { detail: "测试请求已拦截，不启动真实调研" } });
  });
  await page.getByRole("button").filter({ hasText: "重新分析" }).click();
  await expect.poll(() => submitted?.refresh_dimensions).toEqual(["events"]);
  await page.setViewportSize({ width: 390, height: 844 });
  await page.screenshot({ path: "/tmp/industry-chain-quality-mobile.png", fullPage: true });
  expect(await page.evaluate(() => document.documentElement.scrollWidth <= window.innerWidth + 1)).toBe(true);
});

for (const viewport of [{ width: 1440, height: 1000 }, { width: 390, height: 844 }]) {
  test(`company research content uses the full row width at ${viewport.width}px`, async ({ page }) => {
    await mockIndustryChainPage(page);
    await page.setViewportSize({ width: 1440, height: 1000 });
    const longName = "LongCompanyNameWithoutAnySpaces".repeat(4);
    const longRole = "核心零部件制造与全球供应链协同".repeat(8);
    const rationale = `研究依据与风险说明 ${"https://example.com/research/"}${"long-reference-".repeat(18)}`;
    await page.route(/\/api\/industry-chain\/.*\/archive\//, route => route.fulfill({ json: {
      ...result,
      opportunities: [
        { name: "示例公司", code: "000001", role: "核心零部件", rationale: "已整理公司角色与公开资料。", scoring_version: 2, score_kind: "research_completeness", completeness_score: 75 },
        { name: longName, code: "688001", role: longRole, rationale, scoring_version: 2, score_kind: "research_completeness", completeness_score: 100 },
        { name: "历史公司", code: "600000", role: longRole, total_score: 88 },
      ],
    } }));
    await page.goto(`/industry-chain/${encodeURIComponent("AI算力")}`);
    await page.getByRole("button", { name: /^AI算力产业链研究/ }).click();
    const section = page.getByRole("region", { name: "公司研究资料" });
    await expect(section).toBeVisible();
    await page.setViewportSize(viewport);
    await expect(section.getByText("资料完整度 75%")).toBeVisible();
    await expect(section.getByText("旧版评分已停用")).toBeVisible();
    await section.evaluate(element => element.scrollIntoView({ block: "start" }));
    await page.screenshot({ path: `/tmp/industry-company-research-${viewport.width}.png` });
    const widths = await section.locator("li").evaluateAll(rows => rows.map(row => {
      const styles = getComputedStyle(row);
      const available = row.clientWidth - parseFloat(styles.paddingLeft) - parseFloat(styles.paddingRight);
      const content = row.querySelector(".industry-opportunity-map__content") as HTMLElement;
      return { available, actual: content.getBoundingClientRect().width };
    }));
    expect(widths).toHaveLength(3);
    for (const { available, actual } of widths) {
      expect(actual).toBeGreaterThanOrEqual(available - 2);
    }
    const outside = await section.evaluate(element => {
      const box = element.getBoundingClientRect();
      return [...element.querySelectorAll("header, strong, p, .ant-tag, .ant-typography, .ant-progress, .industry-opportunity-map__title > span")]
        .filter(child => { const rect = child.getBoundingClientRect(); return rect.width && (rect.left < box.left - 1 || rect.right > box.right + 1); })
        .map(child => child.className);
    });
    expect(outside).toEqual([]);
    const progressWidth = await section.locator(".ant-progress").first().evaluate(element => element.getBoundingClientRect().width);
    expect(progressWidth).toBeGreaterThan(200);
    expect(await page.evaluate(() => document.documentElement.scrollWidth <= window.innerWidth + 1)).toBe(true);
  });
}

for (const width of [1440, 390]) {
  test(`shows causal theses and honest verification boundaries at ${width}px`, async ({ page }) => {
    await mockIndustryChainPage(page);
    await page.route(/\/api\/industry-chain\/.*\/archive\//, route => route.fulfill({ json: {
      ...result,
      research_theses: [{ title: "需求增长如何转为现金回款", detail: "订单增加不代表利润和现金流同时改善。",
        chain_path: ["云计算", "服务器集成", "AI芯片"], mechanism: "需求数量与产品结构→订单→交付→验收→收入→回款", conditions: ["客户验收完成"],
        counter_evidence: "本次未取得反向证据", invalidation: "应收账款增速持续高于收入增速", tracking_metrics: ["经营现金流与收入比", "逾期应收账款"],
        claim_type: "inference", verification_status: "unverified", verification_notes: ["仅有检索线索，下一步读取原始财报正文。"],
      }],
      market_metrics: [{ label: "机构市场预测", value: "100亿元", evidence_basis: "forecast", verification_status: "quote_matched" }],
      verification_repair: { status: "no_new_evidence", attempted_rounds: 1, added_evidence_count: 0, note: "补证未取得新增正文，保留原有缺口。" },
    } }));
    await page.setViewportSize({ width: 1440, height: 1000 });
    await page.goto(`/industry-chain/${encodeURIComponent("AI算力")}`);
    await page.getByRole("button", { name: /^AI算力产业链研究/ }).click();
    await page.setViewportSize({ width, height: 1000 });
    const theses = page.getByRole("region", { name: "核心研究判断" });
    await expect(theses.getByText("前提证据不足 · 待验证")).toBeVisible();
    await expect(theses.getByText("云计算 → 服务器集成 → AI芯片")).toBeVisible();
    await expect(theses.getByText("需求数量与产品结构→订单→交付→验收→收入→回款")).toBeVisible();
    await expect(theses.getByText("应收账款增速持续高于收入增速")).toBeVisible();
    await theses.scrollIntoViewIfNeeded();
    await page.screenshot({ path: `/tmp/industry-depth-${width}.png` });
    await page.getByRole("button", { name: "关键结论核验 · 原文匹配不等于事实核实" }).click();
    await page.getByRole("radio", { name: "来源机构预测", exact: true }).check();
    await page.getByRole("radio", { name: "只看待验证" }).check();
    await expect(page.getByText("当前筛选下没有结论")).toBeVisible();
    await page.getByRole("radio", { name: "研究推断", exact: true }).check();
    await expect(page.getByText("仅有检索线索，下一步读取原始财报正文。")).toBeVisible();
    expect(await page.evaluate(() => document.documentElement.scrollWidth <= innerWidth + 1)).toBe(true);
  });
}

for (const width of [1440, 390]) {
  test(`hides internal evidence references throughout the report at ${width}px`, async ({ page }) => {
    await mockIndustryChainPage(page);
    await page.route(/\/api\/industry-chain\/.*\/archive\//, route => route.fulfill({ json: {
      ...result,
      summary: "核心结论（证据 ev_report）",
      upstream: [{ name:"AI芯片", role:"依据ev_report形成角色说明", evidence_ids:["ev_report"] }],
      research_theses: [{title:"核心判断ev_report", mechanism:"需求形成订单（ev_report）"}],
      warnings:["原文缺失：ev_unknown"],
      evidence_catalog:[{evidence_id:"ev_report",tool_name:"web_fetch",title:"示例公司公告",source_urls:["https://example.com/report"],content_preview:"原文摘录 ev_report",arguments:'{"note":"ev_report"}'}],
      llm_review:"## 历史正文\n结论（证据 `ev_report`）\n\n[公司公告原文](https://example.com/report)",
    } }));
    await page.setViewportSize({width:1440,height:1000});
    await page.goto(`/industry-chain/${encodeURIComponent("AI算力")}`);
    await page.getByRole("button",{name:/^AI算力产业链研究/}).click();
    await page.setViewportSize({width,height:1000});
    // Include collapsed DOM contents, not just the default-visible cards.
    expect(await page.locator("body").textContent()).not.toMatch(/ev_[a-z0-9_]+/i);
    await page.getByRole("button",{name:/完整研究正文/}).click();
    await expect(page.getByRole("link",{name:"公司公告原文"})).toHaveAttribute("href","https://example.com/report");
    expect(await page.locator("body").textContent()).not.toMatch(/ev_[a-z0-9_]+/i);
    await page.screenshot({path:`/tmp/industry-no-ev-${width}.png`});
  });
}
