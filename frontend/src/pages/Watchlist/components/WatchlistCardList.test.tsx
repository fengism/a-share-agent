import { act, fireEvent, render, screen } from "@testing-library/react";
import { MemoryRouter } from "react-router-dom";
import { describe, expect, it, vi } from "vitest";
import { WatchlistCardList } from "./WatchlistCardList";
import type { WatchlistItem } from "../../../types/watchlist";
import { COPILOT_OPEN_EVENT } from "../../../utils/copilotEvents";

const mockItem: WatchlistItem = {
  id: 1,
  stock_code: "600519",
  stock_name: "贵州茅台",
  note: "",
  created_at: "2026-08-20T10:00:00",
  current_price: 1518.2,
  change_pct: 1.26,
  open_price: 1502,
  high_price: 1522.8,
  low_price: 1498.5,
  previous_close: 1499.31,
  volume: 2300000,
  amount: 3480000000,
  turnover_pct: 0.19,
  pe_ttm: 23.45,
  market_cap: 1905000000000,
  quote_source: "tencent",
  concepts: [{ code: "BK0896", name: "白酒概念" }],
  alerts: [],
};

describe("WatchlistCardList", () => {
  it("renders stock card information and handles events", () => {
    const onToggleSelect = vi.fn();
    const onSetAlert = vi.fn();
    const onDelete = vi.fn();
    const onSelectConcept = vi.fn();

    render(
      <MemoryRouter>
        <WatchlistCardList
          items={[mockItem]}
          selectedIds={[]}
          onToggleSelect={onToggleSelect}
          onSetAlert={onSetAlert}
          onDelete={onDelete}
          onSelectConcept={onSelectConcept}
        />
      </MemoryRouter>,
    );

    expect(screen.getByText("贵州茅台")).toBeInTheDocument();
    expect(screen.getByText("600519")).toBeInTheDocument();
    expect(screen.getByText("1518.20")).toBeInTheDocument();
    expect(screen.getByText("+1.26%")).toBeInTheDocument();

    const checkbox = screen.getByLabelText("选择贵州茅台");
    fireEvent.click(checkbox);
    expect(onToggleSelect).toHaveBeenCalledWith(1);

    const alertBtn = screen.getByLabelText("设置贵州茅台提醒");
    fireEvent.click(alertBtn);
    expect(onSetAlert).toHaveBeenCalledWith(mockItem);

    const deleteBtn = screen.getByLabelText("移除贵州茅台");
    fireEvent.click(deleteBtn);
    expect(onDelete).toHaveBeenCalledWith(mockItem);
  });

  it("triggers AI diagnosis drawer event on clicking AI体检 button", () => {
    const eventHandler = vi.fn();
    window.addEventListener(COPILOT_OPEN_EVENT, eventHandler);

    render(
      <MemoryRouter>
        <WatchlistCardList
          items={[mockItem]}
          selectedIds={[]}
          onToggleSelect={vi.fn()}
          onSetAlert={vi.fn()}
          onDelete={vi.fn()}
          onSelectConcept={vi.fn()}
        />
      </MemoryRouter>,
    );

    const aiBtn = screen.getByLabelText("AI体检贵州茅台");
    fireEvent.click(aiBtn);

    expect(eventHandler).toHaveBeenCalled();
    const customEvent = eventHandler.mock.calls[0][0] as CustomEvent;
    expect(customEvent.detail.prompt).toContain("贵州茅台");
    expect(customEvent.detail.prompt).toContain("600519");

    window.removeEventListener(COPILOT_OPEN_EVENT, eventHandler);
  });

  it("applies tick flash class when price updates", () => {
    const { rerender } = render(
      <MemoryRouter>
        <WatchlistCardList
          items={[mockItem]}
          selectedIds={[]}
          onToggleSelect={vi.fn()}
          onSetAlert={vi.fn()}
          onDelete={vi.fn()}
          onSelectConcept={vi.fn()}
        />
      </MemoryRouter>,
    );

    const priceEl = screen.getByTestId("watchlist-card-price");
    expect(priceEl.className).toBe("");

    const updatedItem = { ...mockItem, current_price: 1525.0 };
    act(() => {
      rerender(
        <MemoryRouter>
          <WatchlistCardList
            items={[updatedItem]}
            selectedIds={[]}
            onToggleSelect={vi.fn()}
            onSetAlert={vi.fn()}
            onDelete={vi.fn()}
            onSelectConcept={vi.fn()}
          />
        </MemoryRouter>,
      );
    });

    expect(priceEl.className).toBe("tick-flash-up");
  });
});
