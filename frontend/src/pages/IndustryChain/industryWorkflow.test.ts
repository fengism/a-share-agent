import { describe, expect, it } from "vitest";
import { INDUSTRY_CHAIN_STAGES, industryStageIndex } from "./industryWorkflow";

describe("industry workflow stages", () => {
  it("maps backend stage codes without relying on fallback positions", () => {
    expect(INDUSTRY_CHAIN_STAGES.map((stage) => stage.code)).toEqual(["research", "synthesis"]);
    expect(industryStageIndex("research")).toBe(0);
    expect(industryStageIndex("synthesis")).toBe(1);
    expect(industryStageIndex("unknown")).toBe(-1);
  });
});
