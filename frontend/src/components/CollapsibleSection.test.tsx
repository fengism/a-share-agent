import { fireEvent, render, screen } from "@testing-library/react";
import { describe, expect, it, vi } from "vitest";
import CollapsibleSection from "./CollapsibleSection";

describe("CollapsibleSection", () => {
  it("starts collapsed by default and toggles on click", () => {
    render(
      <CollapsibleSection id="sec" title="政策与事件传导" summary="3 条">
        <div>正文内容</div>
      </CollapsibleSection>,
    );

    const trigger = screen.getByRole("button", { name: /政策与事件传导/ });
    expect(trigger).toHaveAttribute("aria-expanded", "false");
    expect(screen.queryByText("正文内容")).not.toBeVisible();

    fireEvent.click(trigger);

    expect(trigger).toHaveAttribute("aria-expanded", "true");
    expect(screen.getByText("正文内容")).toBeVisible();
    expect(screen.getByText("3 条")).toBeInTheDocument();
  });

  it("honours defaultOpen", () => {
    render(
      <CollapsibleSection id="sec" title="市场图谱" defaultOpen>
        <div>图谱</div>
      </CollapsibleSection>,
    );

    expect(screen.getByRole("button", { name: /市场图谱/ })).toHaveAttribute("aria-expanded", "true");
    expect(screen.getByText("图谱")).toBeVisible();
  });

  it("supports controlled state and reports changes", () => {
    const onOpenChange = vi.fn();
    render(
      <CollapsibleSection id="sec" title="明日三情景预案" open={false} onOpenChange={onOpenChange}>
        <div>内容</div>
      </CollapsibleSection>,
    );

    fireEvent.click(screen.getByRole("button", { name: /明日三情景预案/ }));

    expect(onOpenChange).toHaveBeenCalledWith(true);
    // 受控时展开状态由外部决定
    expect(screen.getByRole("button", { name: /明日三情景预案/ })).toHaveAttribute("aria-expanded", "false");
  });
});
