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
      upstream: [
        { name: "高纯石英材料", role: "设备反应腔耗材", companies: ["石英股份"], metric: "市占率 40%" },
      ],
      relationships: [
        {
          source_node: "高纯石英材料",
          target_node: "刻蚀与薄膜沉积设备",
          relation_type: "supply",
          title: "国产高纯石英良率提升，支撑刻蚀机出货",
          impact_direction: "positive",
          driver: "海外限供倒逼国产化",
          detail: "国产高纯石英良率提升，支撑刻蚀机出货",
          conditions: ["高纯砂纯度达标"],
        },
      ],
      risks: [
        "地缘政治摩擦与关键零部件出口管制风险。",
      ],
    };
    const md = buildIndustryReportMarkdown(result as IndustryChainResult);
    expect(md).toContain("# 半导体设备 产业链投研报告");
    expect(md).toContain("半导体设备国产化替代进程加速。");
    expect(md).toContain("### 1. 先进制程突破");
    expect(md).toContain("北方华创");
    expect(md).toContain("## 四、上下游环节与价值分布");
    expect(md).toContain("高纯石英材料");
    expect(md).toContain("## 五、产业链传导机制与核心假设");
    expect(md).toContain("海外限供倒逼国产化");
    expect(md).toContain("## 六、潜在风险与跟踪提示");
  });
});
