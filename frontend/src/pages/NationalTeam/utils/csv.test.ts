import { describe, expect, it } from "vitest";

import { escapeCsvCell, serializeCsvRows } from "./csv";

describe("escapeCsvCell", () => {
  it("neutralizes spreadsheet formula prefixes", () => {
    expect(escapeCsvCell("=1+1")).toBe("'=1+1");
    expect(escapeCsvCell("+cmd|'/c calc'!A0")).toBe("'+cmd|'/c calc'!A0");
    expect(escapeCsvCell("@SUM(A1)")).toBe("'@SUM(A1)");
  });

  it("keeps negative numbers readable instead of quoting them", () => {
    expect(escapeCsvCell("-3.25")).toBe("-3.25");
    expect(escapeCsvCell(-3.25)).toBe("-3.25");
    // 带千分位逗号仍需要引号包裹，但不能加发引号式的公式防护前缀。
    expect(escapeCsvCell("-1,234.50")).toBe('"-1,234.50"');
    expect(escapeCsvCell("-12.30 亿元")).toBe("-12.30 亿元");
  });

  it("still escapes a leading minus that is not a number", () => {
    expect(escapeCsvCell("-2+3+cmd")).toBe("'-2+3+cmd");
  });

  it("quotes separators, quotes and newlines", () => {
    expect(escapeCsvCell("华泰柏瑞,基金")).toBe('"华泰柏瑞,基金"');
    expect(escapeCsvCell('华夏"基金')).toBe('"华夏""基金"');
    expect(escapeCsvCell("第一行\n第二行")).toBe('"第一行\n第二行"');
  });

  it("renders nullish values as empty", () => {
    expect(escapeCsvCell(null)).toBe("");
    expect(escapeCsvCell(undefined)).toBe("");
  });
});

describe("serializeCsvRows", () => {
  it("joins rows with CRLF and prefixes a BOM", () => {
    const content = serializeCsvRows([
      ["代码", "名称"],
      ["510300", "华泰柏瑞沪深300ETF"],
    ]);
    expect(content.startsWith("\uFEFF")).toBe(true);
    expect(content).toBe("\uFEFF代码,名称\r\n510300,华泰柏瑞沪深300ETF");
  });
});
