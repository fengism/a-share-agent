import { describe, expect, it } from "vitest";
import { extractBestString, tryExtractFromJson } from "./reportHelpers";

describe("industry-chain report helpers", () => {
  it("prefers known report fields", () => {
    expect(extractBestString({ summary: "这是一段足够长的产业链摘要内容" })).toBe("这是一段足够长的产业链摘要内容");
  });

  it("extracts reports from JSON surrounded by text", () => {
    expect(tryExtractFromJson('prefix {"llm_review":"这是一段足够长的产业链报告内容"} suffix')).toBe(
      "这是一段足够长的产业链报告内容",
    );
  });

  it("keeps non-JSON content unchanged", () => {
    expect(tryExtractFromJson("普通 Markdown 报告")).toBe("普通 Markdown 报告");
  });
});
