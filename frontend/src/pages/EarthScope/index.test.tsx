import { fireEvent, render, screen } from "@testing-library/react";
import { MemoryRouter } from "react-router-dom";
import { describe, expect, it, vi } from "vitest";
import EarthScopeLanding from "./index";

describe("EarthScopeLanding", () => {
  it("renders the landing page hierarchy and navigation", () => {
    const view = render(<MemoryRouter><EarthScopeLanding /></MemoryRouter>);
    expect(document.documentElement).toHaveClass("earthscope-scroll-smooth");
    expect(screen.getByRole("heading", { name: /Satellite data/ })).toBeInTheDocument();
    expect(screen.getByRole("link", { name: /Start building free/ })).toHaveAttribute("href", "/register");
    expect(screen.getByRole("navigation", { name: "EarthScope navigation" })).toBeInTheDocument();
    expect(screen.getByText("148 active feeds")).toBeInTheDocument();
    view.unmount();
    expect(document.documentElement).not.toHaveClass("earthscope-scroll-smooth");
  });

  it("switches billing, API examples, and FAQ content", () => {
    const writeText = vi.fn().mockResolvedValue(undefined);
    Object.defineProperty(navigator, "clipboard", { configurable: true, value: { writeText } });
    render(<MemoryRouter><EarthScopeLanding /></MemoryRouter>);

    expect(screen.getByText("$119")).toBeInTheDocument();
    fireEvent.click(screen.getByRole("button", { name: "Monthly" }));
    expect(screen.getByText("$149")).toBeInTheDocument();

    fireEvent.click(screen.getByRole("button", { name: /Run analysis/ }));
    expect(screen.getByText("/v1/analytics/run")).toBeInTheDocument();
    fireEvent.click(screen.getByRole("button", { name: /Copy example/ }));
    expect(writeText).toHaveBeenCalledWith(expect.stringContaining("earthscope.analytics.run"));

    fireEvent.click(screen.getByRole("button", { name: /Can I use my own cloud storage/ }));
    expect(screen.getByText(/customer-managed object storage/)).toBeInTheDocument();
  });
});
