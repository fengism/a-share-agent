import { fireEvent, render, screen } from "@testing-library/react";
import { beforeEach, describe, expect, it, vi } from "vitest";
import ResponsiveSectionNav from "./ResponsiveSectionNav";

const mocks = vi.hoisted(() => ({
  useMediaQuery: vi.fn(),
}));

vi.mock("../hooks/useMediaQuery", () => ({
  useMediaQuery: (query: string) => mocks.useMediaQuery(query),
}));

describe("ResponsiveSectionNav", () => {
  beforeEach(() => {
    mocks.useMediaQuery.mockReset().mockReturnValue(true);
  });

  it("uses a page-specific collapse width so crowded navigation remains fully selectable", () => {
    render(
      <ResponsiveSectionNav
        activeKey="northbound"
        onChange={vi.fn()}
        ariaLabel="市场数据分类"
        collapseQuery="(max-width: 1024px)"
        items={[
          { key: "market", label: "A股大盘", children: <div>大盘内容</div> },
          { key: "northbound", label: "北向资金", children: <div>北向资金内容</div> },
        ]}
      />,
    );

    expect(mocks.useMediaQuery).toHaveBeenCalledWith("(max-width: 1024px)");
    expect(screen.getByRole("combobox", { name: "市场数据分类" })).toBeInTheDocument();
    expect(screen.getByText("北向资金内容")).toBeInTheDocument();
  });

  it("renders horizontally scrollable chips on mobile when mobileMode=chips", () => {
    const onChange = vi.fn();
    render(
      <ResponsiveSectionNav
        activeKey="ai"
        onChange={onChange}
        ariaLabel="系统配置分类"
        mobileMode="chips"
        items={[
          { key: "account", label: "账号与安全", children: <div>账号内容</div> },
          { key: "ai", label: "AI 模型配置", children: <div>AI 内容</div> },
        ]}
      />,
    );

    const chips = screen.getAllByRole("tab");
    expect(chips).toHaveLength(2);
    expect(screen.queryByRole("combobox")).not.toBeInTheDocument();
    expect(screen.getByRole("tab", { name: "AI 模型配置" })).toHaveAttribute("aria-selected", "true");

    fireEvent.click(screen.getByRole("tab", { name: "账号与安全" }));
    expect(onChange).toHaveBeenCalledWith("account");
  });

  it("keeps the select control on mobile by default", () => {
    render(
      <ResponsiveSectionNav
        activeKey="account"
        onChange={vi.fn()}
        ariaLabel="系统配置分类"
        items={[
          { key: "account", label: "账号与安全", children: <div>账号内容</div> },
        ]}
      />,
    );

    expect(screen.getByRole("combobox", { name: "系统配置分类" })).toBeInTheDocument();
    expect(screen.queryByRole("tab")).not.toBeInTheDocument();
  });

  it("preloads desktop tabs on pointer intent and before selection", () => {
    mocks.useMediaQuery.mockReturnValue(false);
    const preloadMarket = vi.fn();
    const preloadFlow = vi.fn();
    const onChange = vi.fn();

    render(
      <ResponsiveSectionNav
        activeKey="market"
        onChange={onChange}
        ariaLabel="市场数据分类"
        items={[
          { key: "market", label: "A股大盘", onIntent: preloadMarket, children: <div>大盘内容</div> },
          { key: "flow", label: "北向资金", onIntent: preloadFlow, children: <div>北向资金内容</div> },
        ]}
      />,
    );

    fireEvent.pointerEnter(screen.getByText("北向资金"));
    expect(preloadFlow).toHaveBeenCalledTimes(1);

    fireEvent.click(screen.getByRole("tab", { name: "北向资金" }));
    expect(preloadFlow).toHaveBeenCalledTimes(2);
    expect(onChange).toHaveBeenCalledWith("flow");
    expect(preloadMarket).not.toHaveBeenCalled();
  });

  it("preloads rail sections when keyboard focus expresses intent", () => {
    mocks.useMediaQuery.mockReturnValue(false);
    const preload = vi.fn();

    render(
      <ResponsiveSectionNav
        activeKey="overview"
        onChange={vi.fn()}
        ariaLabel="分析维度"
        desktopMode="rail"
        items={[
          { key: "overview", label: "总览", children: <div>总览内容</div> },
          { key: "technical", label: "技术面", onIntent: preload, children: <div>技术内容</div> },
        ]}
      />,
    );

    fireEvent.focus(screen.getByRole("button", { name: "技术面" }));
    expect(preload).toHaveBeenCalledTimes(1);
  });

  it("keeps visited mobile sections mounted without eagerly mounting unvisited content", () => {
    const items = [
      { key: "editor", label: "参数编辑", children: <input aria-label="回测名称草稿" defaultValue="初始名称" /> },
      { key: "result", label: "结果分析", children: <div>结果内容</div> },
    ];
    const { rerender } = render(
      <ResponsiveSectionNav
        activeKey="editor"
        onChange={vi.fn()}
        ariaLabel="保活导航"
        preserveVisited
        items={items}
      />,
    );

    fireEvent.change(screen.getByLabelText("回测名称草稿"), { target: { value: "未提交名称" } });
    expect(screen.queryByText("结果内容")).not.toBeInTheDocument();

    rerender(
      <ResponsiveSectionNav
        activeKey="result"
        onChange={vi.fn()}
        ariaLabel="保活导航"
        preserveVisited
        items={items}
      />,
    );
    expect(screen.getByText("结果内容")).toBeInTheDocument();

    rerender(
      <ResponsiveSectionNav
        activeKey="editor"
        onChange={vi.fn()}
        ariaLabel="保活导航"
        preserveVisited
        items={items}
      />,
    );
    expect(screen.getByLabelText("回测名称草稿")).toHaveValue("未提交名称");
  });

  it("releases an opted-out visited panel while preserving editor state", () => {
    const items = [
      { key: "editor", label: "参数编辑", children: <input aria-label="保活参数" defaultValue="初始值" /> },
      { key: "result", label: "结果分析", preserve: false, children: <div>重型结果内容</div> },
    ];
    const { rerender } = render(
      <ResponsiveSectionNav
        activeKey="editor"
        onChange={vi.fn()}
        ariaLabel="选择性保活导航"
        preserveVisited
        items={items}
      />,
    );
    fireEvent.change(screen.getByLabelText("保活参数"), { target: { value: "编辑后" } });

    rerender(
      <ResponsiveSectionNav
        activeKey="result"
        onChange={vi.fn()}
        ariaLabel="选择性保活导航"
        preserveVisited
        items={items}
      />,
    );
    expect(screen.getByText("重型结果内容")).toBeInTheDocument();

    rerender(
      <ResponsiveSectionNav
        activeKey="editor"
        onChange={vi.fn()}
        ariaLabel="选择性保活导航"
        preserveVisited
        items={items}
      />,
    );
    expect(screen.queryByText("重型结果内容")).not.toBeInTheDocument();
    expect(screen.getByLabelText("保活参数")).toHaveValue("编辑后");
  });
});
