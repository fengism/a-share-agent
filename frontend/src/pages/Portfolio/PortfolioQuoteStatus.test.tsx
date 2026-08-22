import { render, screen } from "@testing-library/react";
import { describe, expect, it } from "vitest";
import PortfolioQuoteStatus from "./PortfolioQuoteStatus";

describe("PortfolioQuoteStatus", () => {
  it("warns when cached quotes are being used", () => {
    render(
      <PortfolioQuoteStatus
        quotedAt="2026-08-13 10:00"
        source="tencent+cache"
        stale
      />,
    );

    expect(screen.getByText("缓存行情")).toBeInTheDocument();
    expect(screen.getByText(/行情可能已经过期/)).toBeInTheDocument();
    expect(screen.getByText(/tencent\+cache/)).toBeInTheDocument();
  });
});
