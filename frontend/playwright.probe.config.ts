import { defineConfig, devices } from "@playwright/test";

// 生产构建下的探针配置：dev server 以 <style> 注入路由 CSS，时序与生产 <link> 不同，
// 同特异性平局的胜负可能相反，因此样式等价性必须在生产产物上测量。
export default defineConfig({
  testDir: "./e2e",
  fullyParallel: true,
  timeout: 60_000,
  expect: { timeout: 10_000 },
  use: { baseURL: "http://127.0.0.1:4173", trace: "off" },
  projects: [{ name: "chromium", use: { ...devices["Desktop Chrome"] } }],
  webServer: {
    command: process.env.SKIP_BUILD
      ? "npm run preview -- --host 127.0.0.1 --port 4173 --strictPort"
      : "npm run build && npm run preview -- --host 127.0.0.1 --port 4173 --strictPort",
    url: "http://127.0.0.1:4173",
    reuseExistingServer: false,
    timeout: 240_000,
  },
});
