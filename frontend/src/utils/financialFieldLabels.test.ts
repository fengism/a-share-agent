import { describe, expect, it } from "vitest";
import { formatFinancialFieldLabel } from "./financialFieldLabels";

describe("formatFinancialFieldLabel", () => {
  it("resolves canonical and Sina-native labels for every statement", () => {
    expect(formatFinancialFieldLabel("TOTAL_CURRENT_ASSETS", "balance")).toBe("流动资产合计");
    expect(formatFinancialFieldLabel("PLAC", "balance")).toBe("拆出资金");
    expect(formatFinancialFieldLabel("BIZTAX", "profit")).toBe("营业税金及附加");
    expect(formatFinancialFieldLabel("BIZTAX_YOY", "profit")).toBe("营业税金及附加同比");
    expect(formatFinancialFieldLabel("DEPONETR", "cashflow")).toBe("客户存款和同业存放款项净增加额");
  });

  it("preserves readable Chinese and hides unknown machine keys", () => {
    expect(formatFinancialFieldLabel("报告期", "balance")).toBe("报告期");
    const unknown = formatFinancialFieldLabel("UNSEEN_PROVIDER_FIELD", "profit");
    expect(unknown).toMatch(/^其他财务字段（\d{4}）$/);
    expect(unknown).not.toContain("UNSEEN_PROVIDER_FIELD");
  });
});
