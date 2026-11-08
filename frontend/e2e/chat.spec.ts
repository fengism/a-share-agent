import { expect, test, type Page } from "./base";

const user = { id: 7, username: "chat-tester", is_admin: false, must_change_password: false };
const config = { disabled_chat_agents: [], disabled_chat_skills: [] };
const capabilities = { agents: [], skills: [] };
const availability = { agents: {}, skills: {} };

async function mockChat(page: Page) {
  await page.route(/^http:\/\/127\.0\.0\.1:4173\/api\//, async (route) => {
    const { pathname } = new URL(route.request().url());
    if (pathname === "/api/auth/me") return route.fulfill({ json: user });
    if (pathname === "/api/config") return route.fulfill({ json: config });
    if (pathname === "/api/chat/capabilities") return route.fulfill({ json: capabilities });
    if (pathname === "/api/chat/capabilities/availability") return route.fulfill({ json: availability });
    return route.fulfill({ json: [] });
  });
}

for (const width of [1440, 390]) {
  test(`chat workspace renders composer at ${width}px`, async ({ page }) => {
    await page.setViewportSize({ width, height: 900 });
    await mockChat(page);

    await page.goto("/chat");

    await expect(page.getByRole("heading", { level: 2, name: /AI 智能投研与选股工作台/ })).toBeVisible();
    await expect(
      page.getByPlaceholder(/输入问题、'\/' 唤起指令或 '\$' 联想股票/),
    ).toBeVisible();
    await expect(page.getByRole("button", { name: "发送" })).toBeVisible();
    await expect(page.getByRole("button", { name: /\/ 指令/ })).toBeVisible();
    await expect(page.locator(".chat-input__quick-chip").first()).toBeVisible();
    expect(
      await page.evaluate(() => document.documentElement.scrollWidth <= window.innerWidth + 1),
    ).toBe(true);
  });
}

test("chat composer keeps its migrated styles at 390px", async ({ page }) => {
  await page.setViewportSize({ width: 390, height: 900 });
  await mockChat(page);

  await page.goto("/chat");
  await expect(page.locator(".chat-input__footer")).toBeVisible();

  const styles = await page.evaluate(() => {
    const read = (sel: string, props: string[]) => {
      const el = document.querySelector(sel);
      if (!el) return null;
      const cs = window.getComputedStyle(el);
      return Object.fromEntries(props.map((p) => [p, cs.getPropertyValue(p)]));
    };
    const root = window.getComputedStyle(document.documentElement);
    return {
      footer: read(".chat-input__footer", ["display", "justify-content", "padding-left"]),
      hint: read(".chat-input__hint", ["font-size"]),
      input: read(".chat-input__row .chat-input__input", ["border-radius", "background-color"]),
      radiusLg: root.getPropertyValue("--c-radius-lg").trim(),
      muted: root.getPropertyValue("--c-text-muted").trim(),
    };
  });

  expect(styles.footer).toMatchObject({
    display: "flex",
    "justify-content": "space-between",
  });
  expect(styles.hint).toMatchObject({ "font-size": "11px" });
  expect(styles.input?.["border-radius"]).toBe(styles.radiusLg);
  expect(styles.input?.["background-color"]).not.toBe("rgba(0, 0, 0, 0)");
  expect(styles.muted).not.toBe("");
});
