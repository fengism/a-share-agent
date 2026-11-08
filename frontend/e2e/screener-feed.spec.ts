import { expect, test, type Page } from "./base";

const user = { id: 9, username: "coverage-tester", is_admin: false, must_change_password: false };

async function mockShell(page: Page) {
  await page.route(/^http:\/\/127\.0\.0\.1:4173\/api\//, async (route) => {
    const pathname = new URL(route.request().url()).pathname;
    if (pathname === "/api/auth/me") return route.fulfill({ json: user });
    return route.fulfill({ json: [] });
  });
}

const noHorizontalOverflow = (page: Page) =>
  page.evaluate(() => document.documentElement.scrollWidth <= window.innerWidth + 1);

for (const width of [1440, 390]) {
  test(`screener workspace renders at ${width}px`, async ({ page }) => {
    await page.setViewportSize({ width, height: 900 });
    await mockShell(page);

    await page.goto("/screener");

    await expect(page.getByText("智能选股")).toBeVisible();
    await expect(page.getByText("历史信号选股（应用于候选范围）")).toBeVisible();
    expect(await noHorizontalOverflow(page)).toBe(true);
  });

  test(`feed renders market and twitter tabs at ${width}px`, async ({ page }) => {
    await page.setViewportSize({ width, height: 900 });
    await mockShell(page);

    await page.goto("/feed");

    await expect(page.getByRole("heading", { name: "资讯中心" })).toBeVisible();
    await expect(page.getByText("市场资讯")).toBeVisible();
    await expect(page.getByText("Twitter 资讯")).toBeVisible();
    expect(await noHorizontalOverflow(page)).toBe(true);
  });
}
