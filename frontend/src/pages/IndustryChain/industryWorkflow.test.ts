import { describe, expect, it } from "vitest";
import { INDUSTRY_CHAIN_STAGES, industryStageIndex } from "./industryWorkflow";

describe("industry workflow stages", () => {
  it("maps backend stage codes without relying on fallback positions", () => {
    expect(INDUSTRY_CHAIN_STAGES.map((stage) => stage.code)).toEqual(["research", "draft", "verification", "finalize", "archive"]);
    expect(industryStageIndex("research")).toBe(0);
    expect(industryStageIndex("draft")).toBe(1);
    expect(industryStageIndex("verification")).toBe(2);
    expect(industryStageIndex("archive")).toBe(4);
    expect(industryStageIndex("unknown")).toBe(-1);
  });
});
