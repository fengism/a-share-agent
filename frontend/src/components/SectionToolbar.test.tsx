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
    const { container } = render(<SectionToolbar ariaLabel="空工具条" />);

    const toolbar = screen.getByRole("group", { name: "空工具条" });
    expect(toolbar).toBeInTheDocument();
    expect(container.querySelector(".section-toolbar__meta")).toBeNull();
    expect(container.querySelector(".section-toolbar__actions")).toBeNull();
  });

  it("renders only actions when meta is omitted", () => {
    const { container } = render(
      <SectionToolbar
        ariaLabel="仅操作工具条"
        actions={<button type="button">导出</button>}
      />,
    );

    expect(screen.getByRole("button", { name: "导出" })).toBeInTheDocument();
    expect(container.querySelector(".section-toolbar__meta")).toBeNull();
    expect(container.querySelector(".section-toolbar__actions")).not.toBeNull();
  });
});
