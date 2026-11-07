import { render, screen } from "@testing-library/react";
import { describe, expect, it } from "vitest";
import SectionToolbar from "./SectionToolbar";

describe("SectionToolbar", () => {
  it("renders both meta and actions with an accessible group label", () => {
    render(
      <SectionToolbar
        ariaLabel="测试工具条"
        meta={<span>更新时间：2026-10-28</span>}
        actions={<button type="button">刷新</button>}
      />,
    );

    const toolbar = screen.getByRole("group", { name: "测试工具条" });
    expect(toolbar).toBeInTheDocument();
    expect(screen.getByText("更新时间：2026-10-28")).toBeInTheDocument();
    expect(screen.getByRole("button", { name: "刷新" })).toBeInTheDocument();
  });

  it("omits empty meta and action containers when props are undefined", () => {
    render(<SectionToolbar ariaLabel="空工具条" />);

    const toolbar = screen.getByRole("group", { name: "空工具条" });
    expect(toolbar).toBeInTheDocument();
    // 不靠类名断言：无 props 时不应产生任何内层容器
    expect(toolbar.querySelectorAll("div")).toHaveLength(0);
  });

  it("renders only actions when meta is omitted", () => {
    render(
      <SectionToolbar
        ariaLabel="仅操作工具条"
        actions={<button type="button">导出</button>}
      />,
    );

    const toolbar = screen.getByRole("group", { name: "仅操作工具条" });
    expect(screen.getByRole("button", { name: "导出" })).toBeInTheDocument();
    expect(toolbar.querySelectorAll("div")).toHaveLength(1);
  });

  it("applies three distinct module-scoped classes", () => {
    render(
      <SectionToolbar
        ariaLabel="样式工具条"
        meta={<span>元信息</span>}
        actions={<button type="button">刷新</button>}
      />,
    );

    const toolbar = screen.getByRole("group", { name: "样式工具条" });
    const [metaBox, actionsBox] = Array.from(toolbar.querySelectorAll("div"));
    const classes = [toolbar.className, metaBox.className, actionsBox.className];

    // CSS Modules 保证每个用法拿到独立类名，且组件根节点必然带类名
    classes.forEach((name) => expect(name).toBeTruthy());
    expect(new Set(classes).size).toBe(3);
  });
});
