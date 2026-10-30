import { fireEvent, render, screen } from "@testing-library/react";
import { MemoryRouter } from "react-router-dom";
import { describe, expect, it, vi } from "vitest";

import ConceptSidePanel from "./ConceptSidePanel";

const ITEMS = [
  { code: "000002", name: "万科A", price: 4.26, change_pct: 4.41, amount: 1, quote_source: "tdxhub" },
  { code: "600519", name: "贵州茅台", price: 1258.62, change_pct: -0.61, amount: 1, quote_source: "tdxhub" },
  { code: "300750", name: "宁德时代", price: 260, change_pct: 2.1, amount: 1, quote_source: "tdxhub" },
  { code: "002230", name: "科大讯飞", price: 48, change_pct: -2.75, amount: 1, quote_source: "tdxhub" },
];

const RELATED = [
  { name: "人形机器人", overlap: 403, ratio: 0.329 },
  { name: "军工", overlap: 88, ratio: 0.07 },
];

function renderPanel(overrides: Partial<Parameters<typeof ConceptSidePanel>[0]> = {}) {
  return render(
    <MemoryRouter>
      <ConceptSidePanel
        concept="机器人概念"
        items={ITEMS}
        related={RELATED}
        changeByName={new Map([["人形机器人", 3.21], ["军工", -1.4]])}
        isLoading={false}
        error={null}
        onRetry={vi.fn()}
        onSelectConcept={vi.fn()}
        {...overrides}
      />
    </MemoryRouter>,
  );
}

describe("ConceptSidePanel", () => {
  it("ranks leaders by change percentage descending", () => {
    renderPanel();

    const names = screen.getAllByRole("link").map((node) => node.textContent?.trim());
    // 领跌列在领涨列之后；领涨第一是万科A(+4.41)
    expect(names.indexOf("万科A")).toBeGreaterThanOrEqual(0);
    expect(names.indexOf("万科A")).toBeLessThan(names.indexOf("贵州茅台"));
  });

  it("lists laggards ascending from the worst", () => {
    const { container } = renderPanel();

    // 领跌列在领涨列之后（document 顺序）：先取领涨列的链接，再取领跌列的
    const cols = container.querySelectorAll(".concept-leaders__col");
    const leaderNames = Array.from(cols[0].querySelectorAll("a")).map((n) => n.textContent?.trim());
    const laggardNames = Array.from(cols[1].querySelectorAll("a")).map((n) => n.textContent?.trim());

    // 领涨列：从高到低；领跌列：最差的排最前
    expect(leaderNames.indexOf("万科A")).toBeLessThan(leaderNames.indexOf("宁德时代"));
    expect(laggardNames[0]).toBe("科大讯飞");
    expect(laggardNames.indexOf("科大讯飞")).toBeLessThan(laggardNames.indexOf("贵州茅台"));
  });

  it("switches concept when a related concept is clicked", () => {
    const onSelectConcept = vi.fn();
    renderPanel({ onSelectConcept });

    fireEvent.click(screen.getByText("人形机器人"));
    expect(onSelectConcept).toHaveBeenCalledWith("人形机器人");
  });

  it("shows each related concept's latest change next to the overlap", () => {
    renderPanel();

    // 人形机器人 +3.21%（来自概念列表的日度聚合），军工 -1.40%
    expect(screen.getByText("+3.21%")).toBeInTheDocument();
    expect(screen.getByText("-1.40%")).toBeInTheDocument();
    expect(screen.getByText("403 只重叠")).toBeInTheDocument();
  });

  it("hides the related-concept card when there is no overlap", () => {
    renderPanel({ related: [] });
    expect(screen.queryByText("关联概念")).not.toBeInTheDocument();
  });

  it("shows a quiet loading hint when quotes have not arrived", () => {
    renderPanel({
      items: [
        { code: "000002", name: "万科A", price: null, change_pct: null, amount: null, quote_source: null },
      ],
    });
    expect(screen.getByText("行情加载中…")).toBeInTheDocument();
  });

  it("shows the error state with a retry", () => {
    const onRetry = vi.fn();
    renderPanel({ items: undefined, error: new Error("boom"), onRetry });
    expect(screen.getByText("成分股加载失败")).toBeInTheDocument();
  });
});
