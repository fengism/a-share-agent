// 统一的 e2e 基座：所有 spec 都从这里导入 test/expect。
// 探针（PROBE_OUT）与密度测量（DENSITY_OUT）由环境变量按需开启，
// 未开启时不产生任何额外行为，因此不再需要临时改 spec 的导入路径。
import { test as base, expect } from "@playwright/test";
import { recordDensity } from "./instrument/density";
import { recordProbe } from "./instrument/probe";

export const test = base.extend({
  // 回调参数不叫 use*，否则会被 react-hooks/rules-of-hooks 误判成 React Hook
  page: async ({ page }, next) => {
    await next(page);

    const title = (base.info().titlePath || []).join(" ").replace(/[^\w\u4e00-\u9fa5]+/g, "_");
    // 先量密度（不修改页面），再做计算样式采样（会注入禁用动画的样式）
    await recordDensity(page, title);
    await recordProbe(page, title);
  },
});

export { expect };
