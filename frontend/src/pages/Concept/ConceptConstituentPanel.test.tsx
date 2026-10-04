import { fireEvent, render, screen, waitFor } from "@testing-library/react";
import { MemoryRouter } from "react-router-dom";
import { describe, expect, it, vi } from "vitest";

import ConceptConstituentPanel from "./ConceptConstituentPanel";
import { closeSourceDate } from "./quoteSource";

const quotes = {
  useConceptConstituents: vi.fn(),
  useConceptIndex: vi.fn(),
  useConceptList: vi.fn(),
};

vi.mock("../../api/queryHooks/concept", () => quotes);

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
        related={[{ name: "人形机器人", overlap: 403, ratio: 0.329 }]}
        total={1225}
        isLoading={false}
        error={null}
        onRetry={vi.fn()}
        quoteSource="tdxhub"
        quoteRequested={ITEMS.length}
        quotePending={false}
        onRequestQuotes={vi.fn()}
        onSelectConcept={vi.fn()}
        {...overrides}
      />
    </MemoryRouter>,
  );
}

describe("ConceptConstituentPanel", () => {
  it("renders constituents with price, change and amount", () => {
    renderPanel();

    expect(screen.getByText("成分股")).toBeInTheDocument();
    // 概览行是「1225 只 · 上涨 x / 下跌 y · 行情 z」拼在一个元素里，用函数匹配
    expect(
      screen.getByText((_, node) => node?.textContent?.startsWith("1225 只") ?? false),
    ).toBeInTheDocument();
    expect(screen.getByText("万科A")).toBeInTheDocument();
    expect(screen.getByText("4.26")).toBeInTheDocument();
    // 5158052352 -> 51.58亿
    expect(screen.getByText("51.58亿")).toBeInTheDocument();
  });

  it("reports intraday breadth from the quotes it actually has", () => {
    renderPanel();
    // 涨 1（万科A）跌 1（贵州茅台），天孚通信无行情不计入
    expect(screen.getByText(/上涨 1 \/ 下跌 1/)).toBeInTheDocument();
  });

  /**
   * 回归：行情按需加载。首屏只应请求一小段代码，而不是全部成分股——
   * 上游按 80 只一批串行，全量请求在上游故障时会等几十秒。
   */
  it("loads only a first window of quotes on mount", async () => {
    const onRequestQuotes = vi.fn();
    renderPanel({ quoteRequested: 0, onRequestQuotes });

    await waitFor(() => expect(onRequestQuotes).toHaveBeenCalledTimes(1));
    const requested = onRequestQuotes.mock.calls[0][0] as string[];
    expect(requested).toEqual(ITEMS.map((item) => item.code));
    expect(requested.length).toBeLessThanOrEqual(80);
  });

  it("marks breadth as partial and offers a full load when coverage is incomplete", async () => {
    const onRequestQuotes = vi.fn();
    // 只加载了 2 只（共 1225 只）→ breadth 标注覆盖量，而不是谎报全量
    renderPanel({ onRequestQuotes, quoteRequested: 2 });

    expect(screen.getByText(/已加载 2 只/)).toBeInTheDocument();
    fireEvent.click(screen.getByText("加载全部行情"));
    expect(onRequestQuotes).toHaveBeenCalledWith(ITEMS.map((item) => item.code));
  });

  /**
   * 回归：缺失行情的股票不能被当成涨跌幅 0 排到中间，
   * 缺失值必须永远沉底，否则"按涨幅"排序会把没数据的股票混进榜单。
   */
  it("sorts missing quotes last regardless of direction", async () => {
    renderPanel();

    // 默认按代码（零上游调用即可出身份列表）；切到按涨幅才会补齐全量行情
    fireEvent.click(screen.getByText("按涨幅"));

    // 涨 4.41（万科A）→ 跌 0.61（贵州茅台）→ 天孚通信(无行情) 沉底
    const links = screen.getAllByRole("link").map((node) => node.textContent?.trim());
    const at = (code: string) => links.indexOf(code);
    expect(at("000002")).toBeGreaterThanOrEqual(0);
    expect(at("000002")).toBeLessThan(at("600519"));
    expect(at("600519")).toBeLessThan(at("300394"));
  });

  it("triggers concept linkage when a related concept tag is clicked", () => {
    const onSelectConcept = vi.fn();
    renderPanel({ onSelectConcept });

    screen.getByText(/人形机器人/).click();
    expect(onSelectConcept).toHaveBeenCalledWith("人形机器人");
  });

  it("shows the error state and retries when the request failed", () => {
    const onRetry = vi.fn();
    render(
      <MemoryRouter>
        <ConceptConstituentPanel
          concept="机器人概念"
          items={undefined}
          related={[]}
          total={0}
          isLoading={false}
          error={new Error("上游炸了")}
          onRetry={onRetry}
          quoteSource={null}
          quoteRequested={0}
          quotePending={false}
          onRequestQuotes={vi.fn()}
          onSelectConcept={vi.fn()}
        />
      </MemoryRouter>,
    );

    expect(screen.getByText("成分股加载失败")).toBeInTheDocument();
  });

  it("hides the related-concept row when there is no overlap", () => {
    renderPanel({ related: [] });
    expect(screen.queryByText("重叠概念")).not.toBeInTheDocument();
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
});