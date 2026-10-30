import { describe, expect, it } from "vitest";
import { enrichStockMentions, parseStockProtocolUrl } from "./stockMarkdownEnhancer";

describe("stockMarkdownEnhancer", () => {
  it("converts stock mentions to stock:// protocol links", () => {
    const input = "推荐关注贵州茅台(600519)与宁德时代（300750）的估值表现。";
    const result = enrichStockMentions(input);

    expect(result).toContain("[贵州茅台 (600519)](stock://600519?name=");
    expect(result).toContain("[宁德时代 (300750)](stock://300750?name=");
  });

  it("does not modify code blocks", () => {
    const input = "```ts\nconst code = '贵州茅台(600519)';\n```\n这里是正文贵州茅台(600519)";
    const result = enrichStockMentions(input);

    expect(result).toContain("const code = '贵州茅台(600519)';");
    expect(result).toContain("[贵州茅台 (600519)](stock://600519?name=");
  });

  it("parses stock protocol url correctly", () => {
    const parsed = parseStockProtocolUrl("stock://600519?name=%E8%B4%B5%E5%B7%9E%E8%8C%85%E5%8F%B0");
    expect(parsed).toEqual({
      code: "600519",
      name: "贵州茅台",
    });

    const parsedNoName = parseStockProtocolUrl("stock://000001");
    expect(parsedNoName).toEqual({
      code: "000001",
      name: undefined,
    });

    const parsedInvalid = parseStockProtocolUrl("https://example.com");
    expect(parsedInvalid).toBeNull();
  });
});
