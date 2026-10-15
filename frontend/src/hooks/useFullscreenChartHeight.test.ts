import { describe, expect, it } from "vitest";
import { computeFullscreenChartHeight } from "./useFullscreenChartHeight";

describe("computeFullscreenChartHeight", () => {
  it("fills the viewport height in landscape (phone held sideways)", () => {
    // 844×390 手机横屏：390 - 88 = 302，且总高度（+头部）不超出视口
    expect(computeFullscreenChartHeight({ width: 844, height: 390 })).toBe(302);
    expect(computeFullscreenChartHeight({ width: 1920, height: 1080 })).toBe(992);
  });

  it("uses a bounded proportional height in portrait", () => {
    expect(computeFullscreenChartHeight({ width: 390, height: 844 })).toBe(574);
    // 很矮的竖屏不低于下限
    expect(computeFullscreenChartHeight({ width: 400, height: 500 })).toBe(360);
    // 很高的竖屏不超过上限
    expect(computeFullscreenChartHeight({ width: 800, height: 2000 })).toBe(760);
  });

  it("keeps a sane minimum on extremely short landscape viewports", () => {
    expect(computeFullscreenChartHeight({ width: 700, height: 200 })).toBe(240);
  });
});
