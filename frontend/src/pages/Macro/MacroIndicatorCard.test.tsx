import { render, screen } from "@testing-library/react";
import { describe, expect, it } from "vitest";
import MacroIndicatorCard from "./MacroIndicatorCard";

describe("MacroIndicatorCard", () => {
  it("shows source, fallback, and stale metadata", () => {
    render(
      <MacroIndicatorCard
        title="CPI"
        latest={{ TIME: "2026-07", VALUE: 0.5 }}
        trend={[]}
        fields={[{ key: "VALUE", label: "同比", unit: "%" }]}
        metadata={{
          latest: null,
          trend: [],
          source: "nbs",
          source_api: "https://data.stats.gov.cn/example",
          latest_period: "2026-07",
          is_fallback: true,
          is_stale: true,
          field_periods: { VALUE: "2025-08" },
          stale_fields: ["VALUE"],
        }}
      />,
    );

    expect(screen.getByText("国家统计局")).toBeInTheDocument();
    expect(screen.getByText("fallback")).toBeInTheDocument();
    expect(screen.getByText("数据滞后")).toBeInTheDocument();
    expect(screen.getByText("滞后")).toBeInTheDocument();
    expect(screen.getByText("2026-07")).toBeInTheDocument();
  });
});
