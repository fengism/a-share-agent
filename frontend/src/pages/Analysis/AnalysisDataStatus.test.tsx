import { render, screen } from "@testing-library/react";
import { describe, expect, it } from "vitest";
import type { AnalysisPageData, AnalysisResult } from "../../types/stock";
import AnalysisDataStatus from "./AnalysisDataStatus";

describe("AnalysisDataStatus", () => {
  it("surfaces unavailable sections and provenance", () => {
    render(
      <AnalysisDataStatus
        pageData={{
          partial: true,
          unavailable_sections: ["valuation", "intraday"],
          stock_info: {
            data_sources: [{ id: "tencent", name: "腾讯行情", provider: "tencent", operation: "quote", api: "quote" }],
          },
          kline: { source: "TDX HTTP", adjustment_verified: false, items: [] },
        } as unknown as AnalysisPageData}
        result={{
          prompt_trace: { model: "deepseek-chat", generated_at: "2026-08-13T10:00:00" },
        } as AnalysisResult}
      />,
    );

    expect(screen.getByText(/估值、分时行情/)).toBeInTheDocument();
    expect(screen.getByText(/复权校验未通过/)).toBeInTheDocument();
    expect(screen.getByText("腾讯行情")).toBeInTheDocument();
    expect(screen.getByText("TDX HTTP")).toBeInTheDocument();
    expect(screen.getByText(/deepseek-chat/)).toBeInTheDocument();
  });
});
