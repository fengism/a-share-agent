import { render, screen } from "@testing-library/react";
import { describe, expect, it } from "vitest";
import { PriceRangeBar } from "./PriceRangeBar";

describe("PriceRangeBar", () => {
  it("renders dash when prices are missing or invalid", () => {
    const { container } = render(<PriceRangeBar low={null} high={null} current={null} />);
    expect(container.textContent).toBe("-");
  });

  it("renders low and high price bounds and range element", () => {
    render(<PriceRangeBar low={10.5} high={12.0} current={11.2} />);
    expect(screen.getByText("10.5")).toBeInTheDocument();
    expect(screen.getByText("12.0")).toBeInTheDocument();
  });
});
