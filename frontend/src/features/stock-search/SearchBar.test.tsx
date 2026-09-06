import { fireEvent, render, screen } from "@testing-library/react";
import { MemoryRouter, useLocation } from "react-router-dom";
import { beforeEach, describe, expect, it, vi } from "vitest";
import SearchBar from "./SearchBar";

const { useStockSearchController } = vi.hoisted(() => ({ useStockSearchController: vi.fn() }));
vi.mock("../../hooks/useStockSearchController", () => ({ useStockSearchController }));

function LocationProbe() {
  const location = useLocation();
  return <span data-testid="location">{location.pathname}</span>;
}

function renderSearch(buildTarget?: (code: string) => string) {
  return render(
    <MemoryRouter>
      <SearchBar buildTarget={buildTarget} />
      <LocationProbe />
    </MemoryRouter>,
  );
}

describe("SearchBar destinations", () => {
  beforeEach(() => {
    useStockSearchController.mockReturnValue({
      inputValue: "600519",
      normalizedInput: "600519",
      currentResults: [{ code: "600519", name: "贵州茅台", price: 1500 }],
      isPending: false,
      isError: false,
      error: null,
      retry: vi.fn(),
      setInputValue: vi.fn(),
      clear: vi.fn(),
      resolveCode: () => "600519",
    });
  });

  it("uses the stock facts route by default when Enter is pressed", () => {
    renderSearch();
    fireEvent.keyDown(screen.getByPlaceholderText(/输入股票代码或名称/), { key: "Enter" });
    expect(screen.getByTestId("location")).toHaveTextContent("/stock/600519");
  });

  it("uses an injected analysis route when Enter is pressed", () => {
    renderSearch((code) => `/analysis/${encodeURIComponent(code)}`);
    fireEvent.keyDown(screen.getByPlaceholderText(/输入股票代码或名称/), { key: "Enter" });
    expect(screen.getByTestId("location")).toHaveTextContent("/analysis/600519");
  });
});
