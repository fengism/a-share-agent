import { fireEvent, render, screen, waitFor } from "@testing-library/react";
import { MemoryRouter, useLocation } from "react-router-dom";
import { beforeEach, describe, expect, it, vi } from "vitest";
import AppHeaderSearch from "./AppHeaderSearch";

const mocks = vi.hoisted(() => ({
  clear: vi.fn(),
  resolveCode: vi.fn(),
  setInputValue: vi.fn(),
}));

vi.mock("../hooks/useStockSearchController", () => ({
  useStockSearchController: () => ({
    inputValue: "600519",
    normalizedInput: "600519",
    currentResults: [],
    isPending: false,
    isError: false,
    error: null,
    retry: vi.fn(),
    setInputValue: mocks.setInputValue,
    clear: mocks.clear,
    resolveCode: mocks.resolveCode,
  }),
}));

vi.mock("../styles/ui", () => ({
  useColors: () => ({
    primary: "#1677ff",
    textPrimary: "#ffffff",
    textSecondary: "#999999",
    up: "#f5222d",
    down: "#52c41a",
  }),
  useTokens: () => ({
    space: [0, 4, 8, 12],
    weight: { medium: 500, semibold: 600 },
    font: { sm: 12, md: 14 },
  }),
}));

function LocationProbe() {
  return <span data-testid="location">{useLocation().pathname}</span>;
}

describe("AppHeaderSearch", () => {
  beforeEach(() => {
    mocks.clear.mockReset();
    mocks.resolveCode.mockReset().mockReturnValue("600519");
    mocks.setInputValue.mockReset();
  });

  it("preserves Enter submission and focuses after deferred activation", async () => {
    render(
      <MemoryRouter initialEntries={["/market"]}>
        <AppHeaderSearch isMobile={false} autoFocus />
        <LocationProbe />
      </MemoryRouter>,
    );

    const input = screen.getByRole("combobox", { name: "搜索股票" });
    expect(input).toHaveFocus();
    fireEvent.keyDown(input, { key: "Enter", code: "Enter", charCode: 13 });

    await waitFor(() => expect(screen.getByTestId("location")).toHaveTextContent("/stock/600519"));
    expect(mocks.resolveCode).toHaveBeenCalledWith("600519");
    expect(mocks.clear).toHaveBeenCalledTimes(1);
  });
});
