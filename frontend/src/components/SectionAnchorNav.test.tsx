import { fireEvent, render, screen } from "@testing-library/react";
import { afterEach, describe, expect, it, vi } from "vitest";
import SectionAnchorNav from "./SectionAnchorNav";

describe("SectionAnchorNav", () => {
  afterEach(() => {
    vi.restoreAllMocks();
    vi.unstubAllGlobals();
  });

  it("renders one chip per section with its badge", () => {
    render(
      <SectionAnchorNav
        ariaLabel="复盘章节导航"
        items={[
          { id: "a", label: "市场图谱" },
          { id: "b", label: "政策与事件传导", badge: "3 条" },
        ]}
      />,
    );

    const nav = screen.getByRole("navigation", { name: "复盘章节导航" });
    expect(nav).toBeInTheDocument();
    expect(screen.getByRole("button", { name: /市场图谱/ })).toHaveAttribute("aria-current", "true");
    expect(screen.getByText("3 条")).toBeInTheDocument();
  });

  it("scrolls to the target anchor and marks it current", () => {
    const target = document.createElement("section");
    target.id = "b";
    target.getBoundingClientRect = () => ({ top: 400, bottom: 0, left: 0, right: 0, width: 0, height: 0, x: 0, y: 0, toJSON: () => ({}) }) as DOMRect;
    document.body.appendChild(target);
    const scrollTo = vi.fn();
    vi.stubGlobal("scrollTo", scrollTo);

    render(
      <SectionAnchorNav
        ariaLabel="复盘章节导航"
        items={[
          { id: "a", label: "市场图谱" },
          { id: "b", label: "政策与事件传导" },
        ]}
      />,
    );

    fireEvent.click(screen.getByRole("button", { name: "政策与事件传导" }));

    expect(scrollTo).toHaveBeenCalledWith({ top: expect.any(Number), behavior: "smooth" });
    expect(screen.getByRole("button", { name: "政策与事件传导" })).toHaveAttribute("aria-current", "true");
    target.remove();
  });

  it("renders nothing without items", () => {
    const { container } = render(<SectionAnchorNav ariaLabel="空" items={[]} />);
    expect(container).toBeEmptyDOMElement();
  });
});
