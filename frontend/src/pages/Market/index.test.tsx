import { fireEvent, render, screen } from "@testing-library/react";
import { MemoryRouter, useLocation } from "react-router-dom";
import { beforeEach, describe, expect, it, vi } from "vitest";

import Market from ".";

function LocationProbe() {
  return <div data-testid="location-probe">{useLocation().search}</div>;
}

const mocks = vi.hoisted(() => ({
  activeKey: "",
  isTradingDay: null as boolean | null,
}));

vi.mock("../../api/queries", () => ({
  useIsTradingDay: () => mocks.isTradingDay,
}));

vi.mock("../../components/ResponsiveSectionNav", () => ({
  default: ({
    activeKey,
    ariaLabel,
    items,
  }: {
    activeKey: string;
    ariaLabel: string;
    items: Array<{ key: string; mobileLabel: string }>;
  }) => {
    mocks.activeKey = activeKey;
    return (
      <nav aria-label={ariaLabel}>
        {items.map((item) => <span key={item.key}>{item.mobileLabel}</span>)}
      </nav>
    );
  },
}));

vi.mock("../../features/hk-market/HKMarketTab", () => ({
  default: ({
    defaultStockCode,
    onStockSelect,
  }: {
    defaultStockCode?: string;
    onStockSelect?: (code: string | null) => void;
  }) => (
    <div data-testid="hk-market-tab">
      港股市场内容{defaultStockCode ? ` - 个股:${defaultStockCode}` : ""}
      <button onClick={() => onStockSelect?.("00700")}>选择腾讯</button>
      <button onClick={() => onStockSelect?.(null)}>清空个股</button>
    </div>
  ),
}));

describe("Market", () => {
  beforeEach(() => {
    mocks.isTradingDay = null;
  });

  it("uses A股大盘 as the default tab and keeps market-specific tabs", () => {
    render(
      <MemoryRouter initialEntries={["/market"]}>
        <Market />
      </MemoryRouter>,
    );

    const navigation = screen.getByRole("navigation", { name: "市场数据分类" });
    expect(mocks.activeKey).toBe("a-index");
    expect(navigation).toHaveTextContent("A股大盘");
    expect(navigation).toHaveTextContent("市场情绪");
    expect(navigation).toHaveTextContent("涨停板");
    expect(navigation).toHaveTextContent("北向资金");
    expect(navigation).toHaveTextContent("融资融券");
    expect(navigation).toHaveTextContent("市场宽度");
    expect(navigation).toHaveTextContent("板块涨跌幅");
    expect(navigation).not.toHaveTextContent("交易日历");
    expect(navigation).toHaveTextContent("龙虎榜");
    expect(navigation).toHaveTextContent("交易所异动");
    expect(navigation).not.toHaveTextContent("市场看板");
  });

  it.each(["overview", "trading-calendar"])("falls back to A股大盘 for removed %s links", (tab) => {
    render(
      <MemoryRouter initialEntries={[`/market?tab=${tab}`]}>
        <Market />
      </MemoryRouter>,
    );

    expect(mocks.activeKey).toBe("a-index");
  });

  it("keeps market data tabs visible on non-trading days", () => {
    mocks.isTradingDay = false;
    render(
      <MemoryRouter initialEntries={["/market"]}>
        <Market />
      </MemoryRouter>,
    );

    const navigation = screen.getByRole("navigation", { name: "市场数据分类" });
    expect(navigation).toHaveTextContent("涨停板");
    expect(navigation).toHaveTextContent("北向资金");
    expect(navigation).toHaveTextContent("板块涨跌幅");
    expect(navigation).toHaveTextContent("龙虎榜");
    expect(navigation).toHaveTextContent("交易所异动");
    expect(navigation).toHaveTextContent("A股大盘");
    expect(navigation).toHaveTextContent("市场情绪");
    expect(navigation).toHaveTextContent("融资融券");
    expect(navigation).toHaveTextContent("市场宽度");
    expect(navigation).not.toHaveTextContent("交易日历");
  });

  it("keeps a directly requested data tab active on a non-trading day", () => {
    mocks.isTradingDay = false;
    render(
      <MemoryRouter initialEntries={["/market?tab=dragon-tiger"]}>
        <Market />
      </MemoryRouter>,
    );

    expect(mocks.activeKey).toBe("dragon-tiger");
    const navigation = screen.getByRole("navigation", { name: "市场数据分类" });
    expect(navigation).toHaveTextContent("龙虎榜");
  });

  it("keeps all tabs on trading days", () => {
    mocks.isTradingDay = true;
    render(
      <MemoryRouter initialEntries={["/market"]}>
        <Market />
      </MemoryRouter>,
    );

    const navigation = screen.getByRole("navigation", { name: "市场数据分类" });
    expect(navigation).toHaveTextContent("涨停板");
    expect(navigation).toHaveTextContent("北向资金");
    expect(navigation).toHaveTextContent("板块涨跌幅");
    expect(navigation).toHaveTextContent("市场宽度");
    expect(navigation).toHaveTextContent("龙虎榜");
    expect(navigation).toHaveTextContent("交易所异动");
  });

  it("keeps the anomaly tab active when requested on a non-trading day", () => {
    mocks.isTradingDay = false;
    render(
      <MemoryRouter initialEntries={["/market?tab=price-anomaly"]}>
        <Market />
      </MemoryRouter>,
    );

    expect(mocks.activeKey).toBe("price-anomaly");
    const navigation = screen.getByRole("navigation", { name: "市场数据分类" });
    expect(navigation).toHaveTextContent("交易所异动");
  });

  it("renders top-level A股 and H股 tabs, defaulting to A股", () => {
    render(
      <MemoryRouter initialEntries={["/market"]}>
        <Market />
      </MemoryRouter>,
    );

    expect(screen.getByRole("tab", { name: /A股/ })).toHaveAttribute("aria-selected", "true");
    expect(screen.getByRole("tab", { name: /H股/ })).toHaveAttribute("aria-selected", "false");
  });

  it("activates the H股 tab when market=hk", async () => {
    render(
      <MemoryRouter initialEntries={["/market?market=hk"]}>
        <Market />
      </MemoryRouter>,
    );

    expect(screen.getByRole("tab", { name: /H股/ })).toHaveAttribute("aria-selected", "true");
    expect(await screen.findByTestId("hk-market-tab")).toBeInTheDocument();
  });

  it("activates the H股 tab when market=h", async () => {
    render(
      <MemoryRouter initialEntries={["/market?market=h"]}>
        <Market />
      </MemoryRouter>,
    );

    expect(screen.getByRole("tab", { name: /H股/ })).toHaveAttribute("aria-selected", "true");
    expect(await screen.findByTestId("hk-market-tab")).toBeInTheDocument();
  });

  it("passes the code query param to HKMarketTab when market=hk&code=00700", async () => {
    render(
      <MemoryRouter initialEntries={["/market?market=hk&code=00700"]}>
        <Market />
      </MemoryRouter>,
    );

    expect(await screen.findByText("港股市场内容 - 个股:00700")).toBeInTheDocument();
  });

  it("updates and clears the code query param via onStockSelect", async () => {
    render(
      <MemoryRouter initialEntries={["/market?market=hk"]}>
        <Market />
        <LocationProbe />
      </MemoryRouter>,
    );

    expect(await screen.findByTestId("hk-market-tab")).toBeInTheDocument();
    expect(screen.getByTestId("location-probe")).not.toHaveTextContent("code=");

    fireEvent.click(screen.getByRole("button", { name: "选择腾讯" }));
    expect(screen.getByTestId("location-probe")).toHaveTextContent("code=00700");

    fireEvent.click(screen.getByRole("button", { name: "清空个股" }));
    expect(screen.getByTestId("location-probe")).not.toHaveTextContent("code=");
  });
});
