import { render, screen } from "@testing-library/react";
import { describe, expect, it } from "vitest";
import DashboardGrid from "./DashboardGrid";

describe("DashboardGrid", () => {
  it("renders children with default 3-column class", () => {
    const { container } = render(
      <DashboardGrid>
        <div>Item 1</div>
        <div>Item 2</div>
        <div>Item 3</div>
      </DashboardGrid>,
    );

    const grid = container.querySelector(".dashboard-grid");
    expect(grid).toBeInTheDocument();
    expect(grid).toHaveClass("dashboard-grid--cols-3");
    expect(screen.getByText("Item 1")).toBeInTheDocument();
  });

  it("supports auto mode and custom gap", () => {
    const { container } = render(
      <DashboardGrid columns="auto" gap={24} minItemWidth={280}>
        <div>Card A</div>
        <div>Card B</div>
      </DashboardGrid>,
    );

    const grid = container.querySelector(".dashboard-grid");
    expect(grid).toHaveClass("dashboard-grid--auto");
  });
});
