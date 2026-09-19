import { fireEvent, render, screen } from "@testing-library/react";
import { MemoryRouter } from "react-router-dom";
import { describe, expect, it, vi } from "vitest";
import HeaderMarketTicker from "./HeaderMarketTicker";

const mockNavigate = vi.fn();
vi.mock("react-router-dom", async () => {
  const actual = await vi.importActual<typeof import("react-router-dom")>("react-router-dom");
  return {
    ...actual,
    useNavigate: () => mockNavigate,
  };
});

vi.mock("../styles/ui", () => ({
  useColors: () => ({
    up: "#ec5d52",
    down: "#3ec98f",
    textSecondary: "#9cafbd",
  }),
}));

const mockUseMarketIndices = vi.fn();
vi.mock("../api/queries", () => ({
  useMarketIndices: () => mockUseMarketIndices(),
}));

describe("HeaderMarketTicker", () => {
  it("renders key index quotes and navigates to market on click", () => {
    mockUseMarketIndices.mockReturnValue({
      data: {
        indices: [
          { code: "000001", name: "上证指数", price: 3042.5, change_pct: 0.62 },
          { code: "399001", name: "深证成指", price: 9850.1, change_pct: -0.15 },
          { code: "399006", name: "创业板指", price: 1980.2, change_pct: 0 },
        ],
      },
    });

    render(
      <MemoryRouter>
        <HeaderMarketTicker />
      </MemoryRouter>,
    );

    expect(screen.getByText("上证")).toBeInTheDocument();
    expect(screen.getByText("3042.50")).toBeInTheDocument();
    expect(screen.getByText("+0.62%")).toBeInTheDocument();

    expect(screen.getByText("深成")).toBeInTheDocument();
    expect(screen.getByText("9850.10")).toBeInTheDocument();
    expect(screen.getByText("-0.15%")).toBeInTheDocument();

    expect(screen.getByText("创指")).toBeInTheDocument();

    fireEvent.click(screen.getByRole("region", { name: "大盘即时指数" }));
    expect(mockNavigate).toHaveBeenCalledWith("/market?tab=a-index");
  });

  it("returns null when indices are empty", () => {
    mockUseMarketIndices.mockReturnValue({ data: { indices: [] } });

    const { container } = render(
      <MemoryRouter>
        <HeaderMarketTicker />
      </MemoryRouter>,
    );

    expect(container.firstChild).toBeNull();
  });
});
