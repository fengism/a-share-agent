import { fireEvent, render, screen, waitFor } from "@testing-library/react";
import { MemoryRouter } from "react-router-dom";
import { beforeEach, describe, expect, it, vi } from "vitest";
import WatchlistPanel from "./WatchlistPanel";

const mocks = vi.hoisted(() => ({
  add: vi.fn(),
  remove: vi.fn(),
  addAlert: vi.fn(),
  search: vi.fn(),
  items: [] as Array<Record<string, unknown>>,
}));

const defaultItem = {
  id: 1,
  stock_code: "601991",
  stock_name: "大唐发电",
  note: "",
  created_at: "2026-08-13T10:00:00",
  current_price: 3.25,
  change_pct: 1.2,
  quote_source: "tencent",
  alerts: [],
};

vi.mock("../../api/queries", () => ({
  useWatchlist: () => ({
    data: {
      items: mocks.items,
      source: "tencent",
      quoted_at: "2026-08-13T10:00:00",
    },
    isLoading: false,
    error: null,
    refetch: vi.fn(),
  }),
  useAddWatchlistItem: () => ({ mutateAsync: mocks.add, isPending: false }),
  useDeleteWatchlistItem: () => ({ mutateAsync: mocks.remove, isPending: false }),
  useAddWatchlistAlert: () => ({ mutateAsync: mocks.addAlert, isPending: false }),
  useDeleteWatchlistAlert: () => ({ mutateAsync: vi.fn(), isPending: false }),
}));

vi.mock("../../hooks/useStockSearchController", () => ({
  useStockSearchController: () => ({
    inputValue: "茅台",
    currentResults: [{ code: "600519", name: "贵州茅台", price: 1500, change_pct: 1 }],
    isPending: false,
    isError: false,
    error: null,
    retry: vi.fn(),
    setInputValue: vi.fn(),
    clear: vi.fn(),
  }),
}));

describe("WatchlistPanel", () => {
  beforeEach(() => {
    mocks.add.mockReset().mockResolvedValue({});
    mocks.remove.mockReset().mockResolvedValue({});
    mocks.items.splice(0, mocks.items.length, defaultItem);
  });

  const renderPanel = () => render(
    <MemoryRouter>
      <WatchlistPanel />
    </MemoryRouter>,
  );

  it("adds a searched stock to the current user's watchlist", async () => {
    renderPanel();

    fireEvent.mouseDown(screen.getByRole("combobox", { name: "搜索并添加自选股" }));
    fireEvent.click(await screen.findByText("贵州茅台"));

    await waitFor(() => expect(mocks.add).toHaveBeenCalledWith({ stock_code: "600519", note: "" }));
  });

  it("renders compact metadata and links stocks to the in-app workspace", () => {
    renderPanel();

    expect(screen.getByRole("heading", { name: "我的自选" })).toBeInTheDocument();
    expect(screen.getByText("添加自选")).toBeInTheDocument();
    expect(document.querySelector(".dashboard-watchlist__header")).toBeInTheDocument();
    expect(document.querySelector(".dashboard-watchlist-card .ant-card-head")).not.toBeInTheDocument();
    expect(screen.getByText("1 只")).toBeInTheDocument();
    expect(screen.getByText(/腾讯行情/)).toBeInTheDocument();
    expect(screen.getByText(/10:00/)).toBeInTheDocument();
    expect(screen.getByRole("list")).toHaveClass("dashboard-watchlist");
    expect(screen.getByRole("listitem")).toHaveClass("dashboard-watchlist__item", "is-up");
    expect(document.querySelector(".dashboard-watchlist__quote-cluster")).toHaveTextContent("3.25");
    expect(document.querySelector(".dashboard-watchlist__actions")).toHaveClass("dashboard-watchlist__actions--overlay");
    expect(screen.getByRole("link", { name: /大唐发电/ })).toHaveAttribute("href", "/stock/601991");
    expect(screen.getByRole("button", { name: "设置大唐发电提醒" })).toBeInTheDocument();
    expect(screen.getByRole("button", { name: "移除大唐发电" })).toBeInTheDocument();
  });

  it("removes a stock from the compact action button", () => {
    renderPanel();

    fireEvent.click(screen.getByRole("button", { name: "移除大唐发电" }));
    expect(mocks.remove).toHaveBeenCalledWith("601991");
  });

  it("links Hong Kong stocks to dedicated stock profile page", () => {
    mocks.items.splice(0, mocks.items.length, {
      ...defaultItem,
      stock_code: "00700",
      stock_name: "腾讯控股",
      market: "hk",
    });

    renderPanel();

    expect(screen.getByRole("link", { name: /腾讯控股/ })).toHaveAttribute("href", "/stock/00700");
  });

  it("supports report analysis shortcut and toggling sort direction", () => {
    mocks.items.splice(0, mocks.items.length,
      { ...defaultItem, id: 1, stock_code: "601991", stock_name: "大唐发电", change_pct: 1.2 },
      { ...defaultItem, id: 2, stock_code: "600519", stock_name: "贵州茅台", change_pct: 3.5 },
    );

    renderPanel();

    expect(screen.getByRole("button", { name: "查看大唐发电研报" })).toBeInTheDocument();
    expect(screen.getByRole("button", { name: "查看贵州茅台研报" })).toBeInTheDocument();
    expect(screen.getByRole("button", { name: "回测大唐发电" })).toBeInTheDocument();
    expect(screen.getByRole("button", { name: "回测贵州茅台" })).toBeInTheDocument();

    const sortButton = screen.getByRole("button", { name: "切换自选股排序" });
    expect(sortButton).toBeInTheDocument();
    fireEvent.click(sortButton);

    const refreshButton = screen.getByRole("button", { name: "刷新自选股行情" });
    expect(refreshButton).toBeInTheDocument();
    fireEvent.click(refreshButton);

    const aiButton = screen.getByRole("button", { name: "AI 诊断自选股" });
    expect(aiButton).toBeInTheDocument();
  });
});
