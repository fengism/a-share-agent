import { describe, expect, it } from "vitest";
import type { IndustryChainResult } from "../../types/stock";
import { buildIndustryReportMarkdown } from "./industryReportMarkdown";

describe("buildIndustryReportMarkdown", () => {
  it("builds markdown from llm_review when available", () => {
    const result: Partial<IndustryChainResult> = {
      name: "光伏设备",
      llm_review: "## 产业综述\n\n光伏设备受益于全球清洁能源转型需求持续增长。",
    };
    const md = buildIndustryReportMarkdown(result as IndustryChainResult);
    expect(md).toContain("# 光伏设备 产业链投研报告");
    expect(md).toContain("光伏设备受益于全球清洁能源转型需求持续增长。");
  });

  it("builds structured markdown when llm_review is absent", () => {
    const result: Partial<IndustryChainResult> = {
      name: "半导体设备",
      summary: "半导体设备国产化替代进程加速。",
      research_theses: [
        { title: "先进制程突破", detail: "核心设备加速自研突破。" },
      ],
      key_stocks: [
        { name: "北方华创", code: "002371", role: "刻蚀与沉积设备龙头" },
      ],
    };
    const md = buildIndustryReportMarkdown(result as IndustryChainResult);
    expect(md).toContain("# 半导体设备 产业链投研报告");
    expect(md).toContain("半导体设备国产化替代进程加速。");
    expect(md).toContain("### 1. 先进制程突破");
    expect(md).toContain("北方华创");
  });
});
