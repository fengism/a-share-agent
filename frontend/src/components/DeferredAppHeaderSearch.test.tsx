import { fireEvent, render, screen } from "@testing-library/react";
import { beforeEach, describe, expect, it, vi } from "vitest";
import DeferredAppHeaderSearch from "./DeferredAppHeaderSearch";

const mocks = vi.hoisted(() => ({
  loadAppHeaderSearch: vi.fn(),
}));

vi.mock("./appHeaderSearchLoader", () => ({
  loadAppHeaderSearch: mocks.loadAppHeaderSearch,
}));

describe("DeferredAppHeaderSearch", () => {
  beforeEach(() => {
    mocks.loadAppHeaderSearch.mockReset().mockResolvedValue({
      default: ({ autoFocus }: { autoFocus?: boolean }) => (
        <input aria-label="搜索股票" autoFocus={autoFocus} />
      ),
    });
  });

  it("preloads from intent and focuses the full search after activation", async () => {
    render(<DeferredAppHeaderSearch isMobile={false} />);

    const trigger = screen.getByRole("button", { name: "打开股票搜索" });
    expect(screen.queryByRole("textbox", { name: "搜索股票" })).not.toBeInTheDocument();

    fireEvent.focus(trigger);
    expect(mocks.loadAppHeaderSearch).toHaveBeenCalledTimes(1);
    expect(screen.queryByRole("textbox", { name: "搜索股票" })).not.toBeInTheDocument();

    fireEvent.click(trigger);
    const input = await screen.findByRole("textbox", { name: "搜索股票" });
    expect(input).toHaveFocus();
  });

  it("activates search on Cmd+K keyboard shortcut", async () => {
    render(<DeferredAppHeaderSearch isMobile={false} />);

    expect(screen.queryByRole("textbox", { name: "搜索股票" })).not.toBeInTheDocument();

    fireEvent.keyDown(window, { key: "k", metaKey: true });

    expect(mocks.loadAppHeaderSearch).toHaveBeenCalled();
    const input = await screen.findByRole("textbox", { name: "搜索股票" });
    expect(input).toHaveFocus();
  });
});
