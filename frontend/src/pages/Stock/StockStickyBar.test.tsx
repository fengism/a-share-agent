import { fireEvent, render, screen } from "@testing-library/react";
import { MemoryRouter } from "react-router-dom";
import { describe, expect, it, vi } from "vitest";
import StockStickyBar from "./StockStickyBar";
import { COPILOT_OPEN_EVENT } from "../../utils/copilotEvents";

describe("StockStickyBar", () => {
  it("renders stock details and handles visibility class", () => {
    const onToggleWatchlist = vi.fn();

    const { rerender } = render(
      <MemoryRouter>
        <StockStickyBar
          code="600519"
          name="贵州茅台"
          currentPrice={1688.5}
          changePct={2.35}
          isWatched={false}
          isWatchlistPending={false}
          onToggleWatchlist={onToggleWatchlist}
          visible={false}
        />
      </MemoryRouter>,
    );

    const aside = screen.queryByRole("complementary");
    expect(aside).not.toBeInTheDocument();

    rerender(
      <MemoryRouter>
        <StockStickyBar
          code="600519"
          name="贵州茅台"
          currentPrice={1688.5}
          changePct={2.35}
          isWatched={true}
          isWatchlistPending={false}
          onToggleWatchlist={onToggleWatchlist}
          visible={true}
        />
      </MemoryRouter>,
    );

    const visibleAside = screen.getByRole("complementary");
    expect(visibleAside).toHaveClass("is-visible");
    expect(screen.getByText("贵州茅台")).toBeInTheDocument();
    expect(screen.getByText("600519")).toBeInTheDocument();
    expect(screen.getByText("1688.50")).toBeInTheDocument();
    expect(screen.getByText("+2.35%")).toBeInTheDocument();
  });

  it("handles smooth scroll to top when clicking the stock info area", () => {
    const scrollToMock = vi.fn();
    window.scrollTo = scrollToMock;

    render(
      <MemoryRouter>
        <StockStickyBar
          code="600519"
          name="贵州茅台"
          currentPrice={1688.5}
          changePct={2.35}
          isWatched={false}
          isWatchlistPending={false}
          onToggleWatchlist={vi.fn()}
          visible={true}
        />
      </MemoryRouter>,
    );

    const backToTopBtn = screen.getByLabelText("返回顶部：贵州茅台");
    fireEvent.click(backToTopBtn);

    expect(scrollToMock).toHaveBeenCalledWith({ top: 0, behavior: "smooth" });
  });

  it("handles watchlist toggle and triggers AI copilot event", () => {
    const onToggleWatchlist = vi.fn();
    const eventHandler = vi.fn();
    window.addEventListener(COPILOT_OPEN_EVENT, eventHandler);

    render(
      <MemoryRouter>
        <StockStickyBar
          code="600519"
          name="贵州茅台"
          currentPrice={1688.5}
          changePct={2.35}
          isWatched={false}
          isWatchlistPending={false}
          onToggleWatchlist={onToggleWatchlist}
          visible={true}
        />
      </MemoryRouter>,
    );

    const watchlistBtn = screen.getByLabelText("加入自选");
    fireEvent.click(watchlistBtn);
    expect(onToggleWatchlist).toHaveBeenCalledTimes(1);

    const aiBtn = screen.getByLabelText("AI伴随诊断");
    fireEvent.click(aiBtn);
    expect(eventHandler).toHaveBeenCalled();
    const customEvent = eventHandler.mock.calls[0][0] as CustomEvent;
    expect(customEvent.detail.prompt).toContain("贵州茅台");
    expect(customEvent.detail.prompt).toContain("600519");

    window.removeEventListener(COPILOT_OPEN_EVENT, eventHandler);
  });
});
