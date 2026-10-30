import { expect, test } from "@playwright/test";

for (const width of [1440, 1024, 768, 390]) {
  test(`integration cards align at ${width}px`, async ({ page }) => {
    await page.setViewportSize({ width, height: 1000 });
    await page.route(/^http:\/\/127\.0\.0\.1:4173\/api\//, async (route) => {
      const pathname = new URL(route.request().url()).pathname;
      const body = pathname === "/api/auth/me"
        ? { id: 7, username: "layout-tester", is_admin: false, must_change_password: false }
        : pathname === "/api/config"
          ? { is_admin: false, provider_defaults: {} }
          : [];
      await route.fulfill({ json: body });
    });

    await page.goto("/settings");
    if (width < 768) {
      // 窄屏使用横向胶囊导航（mobileMode="chips"），不再是下拉框
      await page.getByRole("tab", { name: "协同与自动推送", exact: true }).click();
    } else {
      await page.getByRole("button", { name: "协同与自动推送", exact: true }).click();
    }

    const section = page.getByRole("region", { name: "协同与自动推送", exact: true });
    const feishu = section.locator(".ant-card").filter({ hasText: "飞书推送配置" });
    const notion = section.locator(".ant-card").filter({ hasText: "Notion 转存配置" });
    await expect(feishu).toBeVisible();
    await expect(notion).toBeVisible();

    await section.screenshot({ path: test.info().outputPath("content-integrations.png") });
  });
}
