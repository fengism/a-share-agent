import { fireEvent, render, screen } from "@testing-library/react";
import { MemoryRouter, Route, Routes, useLocation } from "react-router-dom";
import { beforeEach, describe, expect, it, vi } from "vitest";
import AnalysisEntry from "./Entry";

const { useStockSearchController } = vi.hoisted(() => ({ useStockSearchController: vi.fn() }));
vi.mock("../../hooks/useStockSearchController", () => ({ useStockSearchController }));
vi.mock("../../features/investment-research/AnalysisHistoryManager", () => ({
  default: () => <div data-testid="mock-history-manager">历史记录</div>,
}));

function LocationProbe() {
  const location = useLocation();
  return <span data-testid="location">{location.pathname}{location.search}</span>;
}

describe("AnalysisEntry", () => {
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

  it("defaults to navigating to stock profile (/stock/:code), not AI analysis", () => {
    render(
      <MemoryRouter initialEntries={["/analysis"]}>
        <Routes>
          <Route path="/analysis" element={<><AnalysisEntry /><LocationProbe /></>} />
          <Route path="/stock/:code" element={<LocationProbe />} />
        </Routes>
      </MemoryRouter>,
    );

    expect(screen.getByText("选择一只股票，进入个股资料页")).toBeInTheDocument();
    fireEvent.keyDown(screen.getByPlaceholderText(/输入股票代码或名称/), { key: "Enter" });
    expect(screen.getByTestId("location")).toHaveTextContent("/stock/600519");
  });

  it("redirects ?code=600519 query param to /analysis/600519", () => {
    render(
      <MemoryRouter initialEntries={["/analysis?code=600519"]}>
        <Routes>
          <Route path="/analysis" element={<AnalysisEntry />} />
          <Route path="/analysis/:code" element={<LocationProbe />} />
        </Routes>
      </MemoryRouter>,
    );

    expect(screen.getByTestId("location")).toHaveTextContent("/analysis/600519");
  });
});
