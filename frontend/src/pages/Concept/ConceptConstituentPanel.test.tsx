import { render, screen } from "@testing-library/react";
import { MemoryRouter } from "react-router-dom";
import { describe, expect, it, vi } from "vitest";

import ConceptConstituentPanel from "./ConceptConstituentPanel";

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
   * 回归：缺失行情的股票不能被当成涨跌幅 0 排到中间，
   * 缺失值必须永远沉底，否则"按涨幅"排序会把没数据的股票混进榜单。
   */
  it("sorts missing quotes last regardless of direction", () => {
    renderPanel();

    // 默认按涨幅降序：万科A(+4.41) → 贵州茅台(-0.61) → 天孚通信(无行情)
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
});