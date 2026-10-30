import { fireEvent, render, screen } from "@testing-library/react";
import { afterEach, describe, expect, it, vi } from "vitest";
import SettingsSectionDirectory from "./SettingsSectionDirectory";

describe("SettingsSectionDirectory", () => {
  afterEach(() => {
    vi.restoreAllMocks();
  });

  it("renders one chip per group and marks the first one as current", () => {
    render(
      <SettingsSectionDirectory
        items={[
          { id: "anchor-a", label: "模型引擎" },
          { id: "anchor-b", label: "模型默认值" },
        ]}
        ariaLabel="AI 模型配置目录"
      />,
    );

    const nav = screen.getByRole("navigation", { name: "AI 模型配置目录" });
    expect(nav).toBeInTheDocument();
    expect(screen.getByRole("button", { name: "模型引擎" })).toHaveAttribute("aria-current", "true");
    expect(screen.getByRole("button", { name: "模型默认值" })).not.toHaveAttribute("aria-current");
  });

  it("scrolls to the matching anchor and highlights the clicked chip", () => {
    const target = document.createElement("div");
    target.id = "anchor-b";
    target.getBoundingClientRect = () => ({ top: 500, bottom: 0, left: 0, right: 0, width: 0, height: 0, x: 0, y: 0, toJSON: () => ({}) }) as DOMRect;
    document.body.appendChild(target);
    const scrollTo = vi.fn();
    vi.stubGlobal("scrollTo", scrollTo);

    render(
      <SettingsSectionDirectory
        items={[
          { id: "anchor-a", label: "模型引擎" },
          { id: "anchor-b", label: "模型默认值" },
        ]}
        ariaLabel="AI 模型配置目录"
      />,
    );

    fireEvent.click(screen.getByRole("button", { name: "模型默认值" }));

    expect(screen.getByRole("button", { name: "模型默认值" })).toHaveAttribute("aria-current", "true");
    expect(scrollTo).toHaveBeenCalledWith({ top: expect.any(Number), behavior: "smooth" });

    target.remove();
    vi.unstubAllGlobals();
  });

  it("renders nothing when there are no groups", () => {
    const { container } = render(<SettingsSectionDirectory items={[]} ariaLabel="空目录" />);
    expect(container).toBeEmptyDOMElement();
  });
});
