import { render, screen } from "@testing-library/react";
import { MemoryRouter } from "react-router-dom";
import { describe, expect, it } from "vitest";
import StockWorkspaceNav from "./StockWorkspaceNav";

describe("StockWorkspaceNav", () => {
  it("links the stock profile and AI analysis workspaces for the current code", () => {
    render(
      <MemoryRouter initialEntries={["/stock/600519"]}>
        <StockWorkspaceNav code="600519" />
      </MemoryRouter>,
    );

    expect(screen.getByRole("link", { name: "个股资料" })).toHaveAttribute("href", "/stock/600519");
    expect(screen.getByRole("link", { name: "个股资料" })).toHaveAttribute("aria-current", "page");
    expect(screen.getByRole("link", { name: "AI 分析" })).toHaveAttribute("href", "/analysis/600519");
  });

  it("marks the AI analysis workspace as active on the analysis route", () => {
    render(
      <MemoryRouter initialEntries={["/analysis/600519"]}>
        <StockWorkspaceNav code="600519" />
      </MemoryRouter>,
    );

    expect(screen.getByRole("link", { name: "AI 分析" })).toHaveAttribute("aria-current", "page");
    expect(screen.getByRole("link", { name: "个股资料" })).not.toHaveAttribute("aria-current");
  });

  it("renders stock profile and watchlist links for HK stock without H market link", () => {
    render(
      <MemoryRouter initialEntries={["/stock/00700"]}>
        <StockWorkspaceNav code="00700" market="hk" />
      </MemoryRouter>,
    );

    expect(screen.getByRole("link", { name: "个股资料" })).toHaveAttribute("href", "/stock/00700");
    expect(screen.getByRole("link", { name: "个股资料" })).toHaveAttribute("aria-current", "page");
    expect(screen.getByRole("link", { name: "我的自选" })).toHaveAttribute("href", "/watchlist");
    expect(screen.queryByRole("link", { name: "H股市场" })).not.toBeInTheDocument();
  });
});
