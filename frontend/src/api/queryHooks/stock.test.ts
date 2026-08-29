import { QueryClient } from "@tanstack/react-query";
import { afterEach, describe, expect, it, vi } from "vitest";
import { queryKeys } from "../queryKeys";
import { openApiGet } from "../openapiClient";
import { ensureFundamentalData } from "./stock";

vi.mock("../openapiClient", async () => {
  const actual = await vi.importActual<typeof import("../openapiClient")>("../openapiClient");
  return { ...actual, openApiGet: vi.fn() };
});

describe("ensureFundamentalData", () => {
  afterEach(() => vi.mocked(openApiGet).mockReset());

  it("refreshes cached data and returns a complete PDF export snapshot", async () => {
    const queryClient = new QueryClient();
    queryClient.setQueryData(queryKeys.stock.financial("600519", "balance"), []);
    queryClient.setQueryData(queryKeys.stock.financial("600519", "profit"), []);
    queryClient.setQueryData(queryKeys.stock.financial("600519", "cashflow"), []);
    queryClient.setQueryData(queryKeys.stock.revenueBreakdown("600519"), {
      by_product: [],
      by_business: [],
      by_region: [],
    });
    vi.mocked(openApiGet).mockImplementation(async (path, args) => {
      if (path === "/api/stock/{code}/revenue-breakdown") {
        return {
          code: "600519",
          symbol: "sh600519",
          name: "贵州茅台",
          source: "sina",
          amount_unit: "CNY_yuan",
          amount_unit_inferred: true,
          by_product: [{ id: "1", class_name: "茅台酒" }],
          by_business: [],
          by_region: [],
        } as never;
      }
      const statementType = (args as { query?: { type?: string } } | undefined)?.query?.type;
      return [{ REPORT_DATE: "2026-06-30", statementType }] as never;
    });

    const snapshot = await ensureFundamentalData(queryClient, "600519");

    expect(openApiGet).toHaveBeenCalledTimes(4);
    expect(snapshot.balance).toHaveLength(1);
    expect(snapshot.profit).toHaveLength(1);
    expect(snapshot.cashflow).toHaveLength(1);
    expect(snapshot.revenueBreakdown.by_product).toHaveLength(1);
    expect(openApiGet).toHaveBeenCalledWith("/api/stock/{code}/financial", {
      path: { code: "600519" },
      query: { type: "balance" },
      options: { timeoutMs: 120_000 },
    });
    expect(openApiGet).toHaveBeenCalledWith("/api/stock/{code}/revenue-breakdown", {
      path: { code: "600519" },
      options: { timeoutMs: 120_000 },
    });
  });

  it("rejects an export snapshot when required financial sections are empty", async () => {
    const queryClient = new QueryClient();
    vi.mocked(openApiGet).mockImplementation(async (path) => (
      path === "/api/stock/{code}/revenue-breakdown"
        ? {
            code: "600519",
            symbol: "sh600519",
            name: "贵州茅台",
            source: "sina",
            amount_unit: "CNY_yuan",
            amount_unit_inferred: true,
            by_product: [],
            by_business: [],
            by_region: [],
          } as never
        : [] as never
    ));

    await expect(ensureFundamentalData(queryClient, "600519")).rejects.toThrow(
      "PDF 导出所需财务数据不完整",
    );
  });
});
