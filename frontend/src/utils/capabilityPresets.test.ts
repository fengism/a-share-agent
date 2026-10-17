import { describe, expect, it, vi } from "vitest";
import {
  CAPABILITY_PRESETS,
  describePresetCatalogDrift,
  reportPresetCatalogDrift,
  resolveCapabilityPreset,
  type CapabilityPresetId,
} from "./capabilityPresets";

/** 与后端能力目录同形且**完整**的候选集——调用方（SkillAgentConfigCard）传的就是完整目录。 */
const CATALOG_SKILLS = [
  "stock_analysis",
  "stock_screening",
  "market_data",
  "url_content",
  "twitter_account",
  "industry_research",
  "information_query",
];
const CATALOG_AGENTS = ["technical", "fundamental", "news", "macro"];

describe("capabilityPresets", () => {
  it("每个预设都有展示元信息与启用规则", () => {
    const ids = CAPABILITY_PRESETS.map((preset) => preset.id);
    expect(new Set(ids).size).toBe(ids.length);
    expect(ids.sort()).toEqual(["full", "low_cost", "news", "quick"]);
    for (const preset of CAPABILITY_PRESETS) {
      expect(preset.label).not.toBe("");
      expect(preset.description).not.toBe("");
    }
  });

  it("full 预设启用目录里全部能力", () => {
    const selection = resolveCapabilityPreset("full", CATALOG_SKILLS, CATALOG_AGENTS);
    expect(selection.skillNames).toEqual(CATALOG_SKILLS);
    expect(selection.agentNames).toEqual(CATALOG_AGENTS);
    expect(selection.unresolvedNames).toEqual([]);
  });

  it("low_cost 预设保留全部 Skill 并关闭全部 Agent", () => {
    const selection = resolveCapabilityPreset("low_cost", CATALOG_SKILLS, CATALOG_AGENTS);
    expect(selection.skillNames).toEqual(CATALOG_SKILLS);
    expect(selection.agentNames).toEqual([]);
    expect(selection.unresolvedNames).toEqual([]);
  });

  it("只保留目录中存在的名字，并按目录顺序返回", () => {
    const selection = resolveCapabilityPreset("quick", CATALOG_SKILLS, CATALOG_AGENTS);
    expect(selection.skillNames).toEqual(["stock_analysis", "stock_screening", "market_data"]);
    expect(selection.agentNames).toEqual(["technical", "fundamental"]);
    expect(selection.unresolvedNames).toEqual([]);
  });

  it("目录中不存在的名字不会进入选中项，并出现在 unresolvedNames", () => {
    const selection = resolveCapabilityPreset("news", ["url_content"], ["news"]);
    expect(selection.skillNames).toEqual(["url_content"]);
    expect(selection.agentNames).toEqual(["news"]);
    expect(selection.unresolvedNames.sort()).toEqual([
      "agent:macro",
      "skill:industry_research",
      "skill:information_query",
      "skill:twitter_account",
    ]);
  });

  it("解析本身不产生副作用（告警只由 reportPresetCatalogDrift 触发）", () => {
    const warn = vi.spyOn(console, "warn").mockImplementation(() => {});
    try {
      // Chat 预设条传入的是按可用性过滤后的子集，缺名属预期，不应告警
      resolveCapabilityPreset("news", [], []);
      expect(warn).not.toHaveBeenCalled();
    } finally {
      warn.mockRestore();
    }
  });

  it("describePresetCatalogDrift 列出所有存在漂移的预设", () => {
    const drifts = describePresetCatalogDrift(["stock_analysis"], []);
    expect(drifts.map((drift) => drift.presetId).sort()).toEqual(["news", "quick"]);
    expect(drifts.find((drift) => drift.presetId === "quick")?.unresolvedNames.sort()).toEqual([
      "agent:fundamental",
      "agent:technical",
      "skill:market_data",
      "skill:stock_screening",
    ]);
    // full 与 low_cost 只引用 "all"/[]，不会漂移
    expect(drifts.some((drift) => drift.presetId === "full")).toBe(false);
    expect(drifts.some((drift) => drift.presetId === "low_cost")).toBe(false);
  });

  it("完整目录下没有漂移", () => {
    expect(describePresetCatalogDrift(CATALOG_SKILLS, CATALOG_AGENTS)).toEqual([]);
  });

  it("reportPresetCatalogDrift 告警一次并对重复漂移去重", async () => {
    // 去重状态是模块级的，用全新的模块实例隔离本用例
    vi.resetModules();
    const { reportPresetCatalogDrift: report } = await import("./capabilityPresets");
    const warn = vi.spyOn(console, "warn").mockImplementation(() => {});
    try {
      // 空目录：两个含具体能力的预设全部漂移
      const first = report([], []);
      expect(first.map((drift) => drift.presetId).sort()).toEqual(["news", "quick"]);
      expect(warn).toHaveBeenCalledTimes(1);

      const message = String(warn.mock.calls[0][0]);
      expect(message).toContain("stock_analysis");
      expect(message).toContain("capabilityPresets.ts");

      // 同样漂移再来一次：已被记录，不再告警也不再返回新漂移
      expect(report([], [])).toEqual([]);
      expect(warn).toHaveBeenCalledTimes(1);

      // 补上部分能力后，剩下的漂移也已报过，依旧不重复告警
      expect(report(["stock_analysis"], [])).toEqual([]);
      expect(warn).toHaveBeenCalledTimes(1);
    } finally {
      warn.mockRestore();
    }
  });

  it("无漂移时不告警", () => {
    const warn = vi.spyOn(console, "warn").mockImplementation(() => {});
    try {
      expect(reportPresetCatalogDrift(CATALOG_SKILLS, CATALOG_AGENTS)).toEqual([]);
      expect(warn).not.toHaveBeenCalled();
    } finally {
      warn.mockRestore();
    }
  });

  it("每个 CapabilityPresetId 都有对应的启用规则", () => {
    // 若新增 preset id 却忘了加规则，resolveCapabilityPreset 会读到 undefined 并抛错
    for (const preset of CAPABILITY_PRESETS) {
      expect(() =>
        resolveCapabilityPreset(preset.id as CapabilityPresetId, CATALOG_SKILLS, CATALOG_AGENTS),
      ).not.toThrow();
    }
  });
});
