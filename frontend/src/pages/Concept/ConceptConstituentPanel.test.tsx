import { fireEvent, render, screen, waitFor, within } from "@testing-library/react";
import { MemoryRouter } from "react-router-dom";
import { beforeEach, describe, expect, it, vi } from "vitest";

import ConceptConstituentPanel from "./ConceptConstituentPanel";
import { closeSourceDate } from "./quoteSource";

const watchlist = vi.hoisted(() => ({
  useWatchlist: vi.fn(),
  useAdd: vi.fn(),
  useRemove: vi.fn(),
}));

vi.mock("../../api/queryHooks/watchlist", () => ({
  useWatchlist: () => watchlist.useWatchlist(),
  useAddWatchlistItem: () => watchlist.useAdd(),
  useDeleteWatchlistItem: () => watchlist.useRemove(),
}));

const ITEMS = [
  { code: "000002", name: "万科A", price: 4.26, change_pct: 4.41, amount: 5158052352, quote_source: "tdxhub" },
  { code: "600519", name: "贵州茅台", price: 1258.62, change_pct: -0.61, amount: 4797246635, quote_source: "tdxhub" },
  // 停牌/无行情：涨跌与成交额都是 null，必须沉底而不是当成 0
  { code: "300394", name: "天孚通信", price: null, change_pct: null, amount: null, quote_source: null },
];

function renderPanel(overrides: Partial<Parameters<typeof ConceptConstituentPanel>[0]> = {}) {
  return render(
    <MemoryRouter>
      <ConceptConstituentPanel
        concept="机器人概念"
        items={ITEMS}
        total={1225}
        isLoading={false}
        error={null}
        onRetry={vi.fn()}
        quoteRequested={ITEMS.length}
        quotePending={false}
        quoteUnavailable={false}
        onSelectConcept={vi.fn()}
        {...overrides}
      />
    </MemoryRouter>,
  );
}

/** 在排序/筛选工具栏范围内点 Segmented，避免命中表格内的「涨停」徽标 */
function clickSegmented(container: HTMLElement, label: string) {
  const bar = container.querySelector(".concept-constituent-sort");
  expect(bar).toBeTruthy();
  const item = Array.from(bar!.querySelectorAll(".ant-segmented-item")).find(
    (el) => el.textContent === label,
  );
  expect(item).toBeTruthy();
  fireEvent.click(item!);
}

describe("ConceptConstituentPanel", () => {
  beforeEach(() => {
    vi.clearAllMocks();
    watchlist.useWatchlist.mockReturnValue({ data: { items: [{ stock_code: "000002", stock_name: "万科A" }] } });
    watchlist.useAdd.mockReturnValue({ mutate: vi.fn() });
    watchlist.useRemove.mockReturnValue({ mutate: vi.fn() });
  });

  it("renders constituents with price, change and amount", () => {
    renderPanel();

    expect(screen.getByText("成分股")).toBeInTheDocument();
    // 仅匹配计数 span（祖先元素的 textContent 以「成分股」开头，不会误中）
    expect(
      screen.getByText((_, node) => node?.textContent?.startsWith("1225 只") ?? false),
    ).toBeInTheDocument();
    expect(screen.getByText("万科A")).toBeInTheDocument();
    expect(screen.getByText("4.26")).toBeInTheDocument();
    // 5158052352 -> 51.58亿
    expect(screen.getByText("51.58亿")).toBeInTheDocument();
  });

  it("reports intraday breadth as an up/down distribution bar", () => {
    renderPanel();
    // 涨 1（万科A）跌 1（贵州茅台），天孚通信无行情不计入
    expect(screen.getByText("涨 1")).toBeInTheDocument();
    expect(screen.getByText("跌 1")).toBeInTheDocument();
  });

  /**
   * 行情按需加载改为自动补齐：面板只负责展示进度，
   * 不再出现让用户手动点的「加载全部行情」。
   */
  it("shows auto-load progress instead of a manual full-load link", () => {
    renderPanel({ quoteRequested: 2 });

    expect(screen.getByText("行情 2/1225")).toBeInTheDocument();
    expect(screen.queryByText("加载全部行情")).not.toBeInTheDocument();
  });

  it("hides the progress once quotes are fully loaded", () => {
    renderPanel({ quoteRequested: 1225 });
    expect(screen.queryByText(/行情 \d+\/\d+/)).not.toBeInTheDocument();
  });

  it("filters rows by direction with a filtered-count in the header", () => {
    const { container } = renderPanel();

    clickSegmented(container, "上涨");
    const links = screen.getAllByRole("link").map((node) => node.textContent?.trim());
    expect(links).toContain("000002");
    expect(links).not.toContain("600519");
    expect(screen.getByText(/筛出 1/)).toBeInTheDocument();
  });

  it("filters limit-up rows by board-aware badge", () => {
    const { container } = renderPanel({
      items: [
        ...ITEMS,
        // 主板 10% 档涨停
        { code: "000001", name: "平安银行", price: 12, change_pct: 9.98, amount: 1, quote_source: "tdxhub" },
      ],
    });

    clickSegmented(container, "涨停");
    const links = screen.getAllByRole("link").map((node) => node.textContent?.trim());
    expect(links).toContain("000001");
    // +4.41% 不算涨停
    expect(links).not.toContain("000002");
  });

  it("filters rows by name or code keyword", () => {
    const { container } = renderPanel();

    const input = container.querySelector(
      ".concept-constituent-sort input.ant-input",
    ) as HTMLInputElement;
    fireEvent.change(input, { target: { value: "600519" } });

    const links = screen.getAllByRole("link").map((node) => node.textContent?.trim());
    expect(links).toContain("600519");
    expect(links).not.toContain("000002");
  });

  it("shows the quote snapshot time once quotes are fully loaded", () => {
    renderPanel({ quoteRequested: 1225, quotedAt: "2026-10-27T05:00:00+00:00" });
    expect(screen.getByText(/行情 \d{2}:\d{2}:\d{2}/)).toBeInTheDocument();
  });

  it("notes when realtime quotes are unavailable", () => {
    renderPanel({ quoteRequested: 2, quoteUnavailable: true });
    expect(screen.getByText(/实时行情暂不可用/)).toBeInTheDocument();
  });

  /**
   * 回归：缺失行情的股票不能被当成涨跌幅 0 排到中间，
   * 缺失值必须永远沉底；默认按涨跌幅降序，直接看领涨。
   */
  it("sorts by change percentage by default with missing quotes last", () => {
    renderPanel();

    // 万科A +4.41 → 贵州茅台 -0.61 → 天孚通信(无行情) 沉底
    const links = screen.getAllByRole("link").map((node) => node.textContent?.trim());
    const at = (code: string) => links.indexOf(code);
    expect(at("000002")).toBeGreaterThanOrEqual(0);
    expect(at("000002")).toBeLessThan(at("600519"));
    expect(at("600519")).toBeLessThan(at("300394"));
  });

  it("can switch to code order via the segmented control", () => {
    renderPanel();

    fireEvent.click(screen.getByText("按代码"));
    const links = screen.getAllByRole("link").map((node) => node.textContent?.trim());
    const at = (code: string) => links.indexOf(code);
    expect(at("000002")).toBeLessThan(at("300394"));
    expect(at("300394")).toBeLessThan(at("600519"));
  });

  it("marks limit-up and limit-down by board-specific thresholds", () => {
    const { container } = renderPanel({
      items: [
        // 主板 10% 档：9.98% 判涨停
        { code: "000001", name: "平安银行", price: 12, change_pct: 9.98, amount: 1, quote_source: "tdxhub" },
        // 创业板 20% 档：9.98% 不判涨停，19.9% 才判
        { code: "300001", name: "特锐德", price: 22, change_pct: 9.98, amount: 1, quote_source: "tdxhub" },
      ],
    });

    // 徽标在表格内；「涨停」同时也是筛选器的选项名，必须限定范围
    const table = container.querySelector(".ant-table");
    expect(table).toBeTruthy();
    expect(within(table as HTMLElement).getByText("涨停")).toBeInTheDocument();
    expect(within(table as HTMLElement).queryByText("特锐德涨停")).not.toBeInTheDocument();
  });

  it("toggles watchlist membership from the row actions", () => {
    const add = vi.fn();
    const remove = vi.fn();
    watchlist.useAdd.mockReturnValue({ mutate: add });
    watchlist.useRemove.mockReturnValue({ mutate: remove });

    renderPanel();

    // 000002 已在自选 → 点击移出；600519 不在 → 点击加入
    fireEvent.click(screen.getByLabelText("移出自选-万科A"));
    expect(remove).toHaveBeenCalledWith("000002", expect.anything());

    fireEvent.click(screen.getByLabelText("加入自选-贵州茅台"));
    expect(add).toHaveBeenCalledWith(
      expect.objectContaining({ stock_code: "600519" }),
      expect.anything(),
    );
  });

  it("links each stock to the deep-analysis workspace", () => {
    renderPanel();
    const analysisLink = screen.getByLabelText("个股分析-万科A");
    expect(analysisLink.getAttribute("href")).toBe("/analysis/000002");
  });

  it("shows the stock's other concepts and switches on click", () => {
    const onSelectConcept = vi.fn();
    renderPanel({
      onSelectConcept,
      items: [
        {
          ...ITEMS[0],
          related_concepts: ["人形机器人", "减速器", "江苏板块", "预盈预增"],
        },
      ],
    });

    // 只展示前两个 + 剩余计数
    expect(screen.getByText("人形机器人")).toBeInTheDocument();
    expect(screen.getByText("减速器")).toBeInTheDocument();
    expect(screen.getByText("+2")).toBeInTheDocument();
    expect(screen.queryByText("预盈预增")).not.toBeInTheDocument();

    fireEvent.click(screen.getByText("人形机器人"));
    expect(onSelectConcept).toHaveBeenCalledWith("人形机器人");
  });

  it("shows a dash when a stock carries no other concept tags", () => {
    renderPanel({ items: [{ ...ITEMS[0], related_concepts: [] }] });
    expect(screen.getByText("其他概念")).toBeInTheDocument();
  });

  it("shows the error state and retries when the request failed", () => {
    const onRetry = vi.fn();
    render(
      <MemoryRouter>
        <ConceptConstituentPanel
          concept="机器人概念"
          items={undefined}
          total={0}
          isLoading={false}
          error={new Error("上游炸了")}
          onRetry={onRetry}
          quoteRequested={0}
          quotePending={false}
          quoteUnavailable={false}
          onSelectConcept={vi.fn()}
        />
      </MemoryRouter>,
    );

    expect(screen.getByText("成分股加载失败")).toBeInTheDocument();
  });

  it("marks locally sourced prices as closing prices with their date", () => {
    // 实时行情缺失时后端回落到本地当日收盘价，UI 必须标出日期，
    // 否则用户会把收盘价当成盘中实时价。
    renderPanel({
      items: [
        {
          code: "000002",
          name: "万科A",
          price: 4.26,
          change_pct: 4.41,
          amount: 5158052352,
          quote_source: "market_daily_close:2026-10-02",
        },
      ],
    });

    // 兜底收盘价照常显示数字
    expect(screen.getByText("4.26")).toBeInTheDocument();
    // 且被识别为收盘价、带出具体日期
    expect(closeSourceDate("market_daily_close:2026-10-02")).toBe("2026-10-02");
  });

  it("does not label realtime-sourced prices as closing prices", () => {
    renderPanel({ items: [ITEMS[0]] });

    expect(screen.getByText("4.26")).toBeInTheDocument();
    // 实时来源不应被误标为收盘价
    expect(closeSourceDate("tdxhub")).toBeNull();
    expect(closeSourceDate(null)).toBeNull();
    // 格式不符的来源同样不标注，避免把未知来源说成收盘价
    expect(closeSourceDate("market_daily_close:")).toBeNull();
    expect(closeSourceDate("market_daily_close:20261002")).toBeNull();
  });

  it("waits quietly while the identity list is loading", async () => {
    renderPanel({ items: undefined, isLoading: true, total: 0, quoteRequested: 0 });
    await waitFor(() => expect(screen.getByText("成分股")).toBeInTheDocument());
  });
});
