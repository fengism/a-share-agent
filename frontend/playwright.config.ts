import { defineConfig, devices } from "@playwright/test";

export default defineConfig({
  testDir: "./e2e",
  fullyParallel: true,
  forbidOnly: Boolean(process.env.CI),
  retries: process.env.CI ? 1 : 0,
  reporter: process.env.CI ? "github" : "list",
  // 用例在 CPU 竞争下（例如并行跑 Docker 构建）会因首屏渲染变慢而在 30s 处超时，
  // 抬高上限避免把资源抖动误报成产品回归。
  timeout: 45_000,
  expect: { timeout: 10_000 },
  use: {
    baseURL: "http://127.0.0.1:4173",
    trace: "retain-on-failure",
  },
  projects: [
    {
      name: "chromium",
      use: { ...devices["Desktop Chrome"] },
    },
  ],
  webServer: {
    command: "npm run dev -- --host 127.0.0.1 --port 4173 --strictPort",
    url: "http://127.0.0.1:4173",
    // 本地也不允许复用已有 dev server：残留进程的模块图停留在旧文件上，页面会抛
    // "Failed to fetch dynamically imported module"，整批用例变成假失败。
    // 端口被占用时直接报错，好过在过期产物上跑出一片绿/红。
    reuseExistingServer: false,
    timeout: 120_000,
  },
});
