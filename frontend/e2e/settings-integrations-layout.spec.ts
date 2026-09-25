import { expect, test, type Locator } from "@playwright/test";

async function bounds(locator: Locator) {
  const box = await locator.boundingBox();
  expect(box).not.toBeNull();
  return box!;
}

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
      await page.getByRole("combobox", { name: "系统配置分类" }).click();
      await page.getByText("内容集成", { exact: true }).click();
    } else {
      await page.getByRole("button", { name: "内容集成", exact: true }).click();
    }

    const section = page.getByRole("region", { name: "内容集成", exact: true });
    const notion = section.locator(".ant-card").filter({ hasText: "Notion 转存配置" });
    const iwencai = section.locator(".ant-card").filter({ hasText: "问财数据源配置" });
    await expect(notion).toBeVisible();
    await expect(iwencai).toBeVisible();
    await expect(iwencai).toContainText("自定义问财地址需要填写个人 API Key");

    const left = await bounds(notion);
    const right = await bounds(iwencai);
    expect(Math.abs(left.width - right.width)).toBeLessThanOrEqual(1);
    if (width >= 992) {
      expect(Math.abs(left.y - right.y)).toBeLessThanOrEqual(1);
      expect(Math.abs(left.height - right.height)).toBeLessThanOrEqual(1);
      expect(right.x - (left.x + left.width)).toBeCloseTo(16, 0);
      const leftButton = await bounds(notion.getByRole("button", { name: "保存 Notion 配置" }));
      const rightButton = await bounds(iwencai.getByRole("button", { name: "保存问财配置" }));
      expect(Math.abs(leftButton.y - rightButton.y)).toBeLessThanOrEqual(1);
      const leftDivider = await bounds(notion.locator(".ant-divider"));
      const rightDivider = await bounds(iwencai.locator(".ant-divider"));
      expect(Math.abs(leftDivider.y - rightDivider.y)).toBeLessThanOrEqual(1);
    } else {
      expect(Math.abs(left.x - right.x)).toBeLessThanOrEqual(1);
      expect(right.y - (left.y + left.height)).toBeCloseTo(16, 0);
      // Stacked cards retain their natural height instead of reserving desktop whitespace.
      expect(right.height).toBeGreaterThan(left.height);
    }
    for (const box of [left, right]) {
      expect(box.x).toBeGreaterThanOrEqual(0);
      expect(box.x + box.width).toBeLessThanOrEqual(width);
    }

    await section.screenshot({ path: test.info().outputPath("content-integrations.png") });
  });
}
