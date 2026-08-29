import { describe, expect, it } from "vitest";
import {
  buildKeyFinancialMetricGroups,
  formatKeyFinancialMetricValue,
} from "./financialStatementPresentation";

function metricValue(
  groups: ReturnType<typeof buildKeyFinancialMetricGroups>,
  groupKey: string,
  metricKey: string,
  periodIndex = 0,
) {
  const group = groups.find((item) => item.key === groupKey);
  const metric = group?.metrics.find((item) => item.key === metricKey);
  return metric?.values[periodIndex];
}

describe("key financial metric presentation", () => {
  it("sorts periods descending and limits every group to four periods", () => {
    const records = [
      "2025-03-31",
      "2026-03-31",
      "2025-06-30",
      "2025-09-30",
      "2025-12-31",
      "2026-03-31",
    ].map((REPORT_DATE, index) => ({
      REPORT_DATE,
      OPERATE_INCOME: 100 + index,
      TOTAL_ASSETS: 200 + index,
      NETCASH_OPERATE: 30 + index,
    }));

    const groups = buildKeyFinancialMetricGroups(records, records, records);

    expect(groups.every((group) => group.periods.length === 4)).toBe(true);
    expect(groups[0].periods.map((period) => period.label)).toEqual([
      "2026-03-31",
      "2025-12-31",
      "2025-09-30",
      "2025-06-30",
    ]);
    expect(metricValue(groups, "profitability", "revenue")).toBe(101);
  });

  it("deduplicates equivalent dates and prefers the latest disclosure", () => {
    const groups = buildKeyFinancialMetricGroups(
      [],
      [
        {
          REPORT_DATE: "20260331",
          NOTICE_DATE: "2026-04-20",
          OPERATE_INCOME: 100,
        },
        {
          REPORT_DATE: "2026-03-31",
          NOTICE_DATE: "20260430",
          OPERATE_INCOME: 120,
        },
      ],
      [],
    );

    expect(groups[0].periods).toHaveLength(1);
    expect(groups[0].periods[0].sortDate).toBe("2026-03-31");
    expect(metricValue(groups, "profitability", "revenue")).toBe(120);
  });

  it("uses Sina aliases and computes derived values", () => {
    const groups = buildKeyFinancialMetricGroups(
      [{
        REPORT_DATE: "2026-06-30",
        TOTASSET: 500,
        TOTLIAB: 200,
        CURFDS: 80,
        INVE: 40,
        TOTCURRASSET: 180,
        TOTALCURRLIAB: 90,
      }],
      [{
        REPORT_DATE: "2026-06-30",
        BIZINCO: 200,
        BIZINCO_YOY: 12.5,
        BIZCOST: 120,
        NETPARECOMPPROF: 50,
        NETPARECOMPPROF_YOY: 8.5,
        BASICEPS: 1.25,
      }],
      [{
        REPORT_DATE: "2026-06-30",
        MANANETR: 75,
        MANANETR_YOY: 15,
        INVNETCASHFLOW: -20,
      }],
    );

    expect(metricValue(groups, "profitability", "revenue")).toBe(200);
    expect(metricValue(groups, "profitability", "gross_margin")).toBe(40);
    expect(metricValue(groups, "profitability", "net_margin")).toBe(25);
    expect(metricValue(groups, "profitability", "basic_eps")).toBe(1.25);
    expect(metricValue(groups, "balance_health", "debt_ratio")).toBe(40);
    expect(metricValue(groups, "balance_health", "current_ratio")).toBe(2);
    expect(metricValue(groups, "cash_quality", "free_cash_flow")).toBe(55);
    expect(metricValue(groups, "cash_quality", "cash_profit_ratio")).toBe(1.5);
  });

  it("does not combine cash flow and profit from different periods", () => {
    const groups = buildKeyFinancialMetricGroups(
      [],
      [{ REPORT_DATE: "2026-03-31", PARENT_NETPROFIT: 50 }],
      [{ REPORT_DATE: "2026-06-30", NETCASH_OPERATE: 75 }],
    );

    expect(metricValue(groups, "cash_quality", "cash_profit_ratio")).toBeNull();
  });

  it("formats missing, amount, percentage, multiple, and EPS values", () => {
    expect(formatKeyFinancialMetricValue(null, "amount")).toBe("-");
    expect(formatKeyFinancialMetricValue(Number.POSITIVE_INFINITY, "amount")).toBe("-");
    expect(formatKeyFinancialMetricValue(12.345, "percent")).toBe("12.35%");
    expect(formatKeyFinancialMetricValue(1.2345, "multiple")).toBe("1.23");
    expect(formatKeyFinancialMetricValue(1.23456, "eps")).toBe("1.2346");
  });
});
