import { expect, test, type Page, type Route } from "@playwright/test";

const admin = {
  id: 7,
  username: "admin",
  is_admin: true,
  must_change_password: false,
};

const regularUser = {
  id: 8,
  username: "researcher",
  is_admin: false,
  must_change_password: false,
};

const maskedAnySearchKey = "keys***alue";

function configResponse(isAdmin: boolean, anysearchApiKey = maskedAnySearchKey) {
  return {
    is_admin: isAdmin,
    provider_defaults: {},
    anysearch_api_key: anysearchApiKey,
  };
}

async function fulfillCommonApi(route: Route, user: typeof admin | typeof regularUser) {
  const pathname = new URL(route.request().url()).pathname;
  if (pathname === "/api/auth/me") {
    await route.fulfill({ json: user });
    return;
  }
  await route.fulfill({ json: [] });
}

async function openDataSources(page: Page) {
  await page.goto("/settings");
  await page.getByRole("button", { name: "数据源管理", exact: true }).click();
}

test("admin can replace AnySearch keys without exposing the masked secret", async ({ page }) => {
  const writes: unknown[] = [];
  await page.route(/^http:\/\/127\.0\.0\.1:4173\/api\//, async (route) => {
    const pathname = new URL(route.request().url()).pathname;
    if (pathname === "/api/config") {
      if (route.request().method() === "PUT") {
        writes.push(route.request().postDataJSON());
        await route.fulfill({ json: configResponse(true, "key-***ey-3") });
      } else {
        await route.fulfill({ json: configResponse(true) });
      }
      return;
    }
    await fulfillCommonApi(route, admin);
  });

  await openDataSources(page);

  const card = page.locator(".ant-card").filter({ hasText: "AnySearch 网页搜索（全局）" });
  const input = card.getByLabel("AnySearch API Key");
  await expect(card).toBeVisible();
  await expect(input).toHaveValue("");
  await expect(input).toHaveAttribute("placeholder", "已配置；输入新的 Key 以覆盖现有配置");
  await expect(card).not.toContainText(maskedAnySearchKey);

  await input.fill(" key-1,key-2,key-3 ");
  await card.getByRole("button", { name: /保存 AnySearch 配置/ }).click();

  await expect.poll(() => writes).toEqual([{ anysearch_api_key: "key-1,key-2,key-3" }]);
  await expect(input).toHaveValue("");
  await expect(input).toHaveAttribute("placeholder", "已配置；输入新的 Key 以覆盖现有配置");
});

test("regular users cannot access the global AnySearch settings", async ({ page }) => {
  await page.route(/^http:\/\/127\.0\.0\.1:4173\/api\//, async (route) => {
    const pathname = new URL(route.request().url()).pathname;
    if (pathname === "/api/config") {
      await route.fulfill({ json: configResponse(false) });
      return;
    }
    await fulfillCommonApi(route, regularUser);
  });

  await page.goto("/settings");

  await expect(page.getByRole("button", { name: "数据源管理", exact: true })).toHaveCount(0);
  await expect(page.getByText("AnySearch 网页搜索（全局）", { exact: true })).toHaveCount(0);
});
