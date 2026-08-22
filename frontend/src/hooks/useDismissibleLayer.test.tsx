import { useState } from "react";
import { fireEvent, render, screen } from "@testing-library/react";
import { describe, expect, it, vi } from "vitest";
import { useDismissibleLayer } from "./useDismissibleLayer";

function Harness({ onDismiss }: { onDismiss: () => void }) {
  const [open, setOpen] = useState(false);
  const dismiss = () => {
    setOpen(false);
    onDismiss();
  };
  const { containerRef, triggerRef } = useDismissibleLayer(open, dismiss);

  return (
    <div ref={containerRef}>
      <button ref={triggerRef} type="button" onClick={() => setOpen(true)}>打开菜单</button>
      {open && <button type="button">菜单项</button>}
    </div>
  );
}

describe("useDismissibleLayer", () => {
  it("keeps inside interaction open and dismisses outside pointers", () => {
    const onDismiss = vi.fn();
    render(<Harness onDismiss={onDismiss} />);

    fireEvent.click(screen.getByRole("button", { name: "打开菜单" }));
    fireEvent.pointerDown(screen.getByRole("button", { name: "菜单项" }));
    expect(screen.getByRole("button", { name: "菜单项" })).toBeInTheDocument();

    fireEvent.pointerDown(document.body);
    expect(screen.queryByRole("button", { name: "菜单项" })).not.toBeInTheDocument();
    expect(onDismiss).toHaveBeenCalledTimes(1);
  });

  it("dismisses on Escape and restores trigger focus", () => {
    const onDismiss = vi.fn();
    render(<Harness onDismiss={onDismiss} />);
    const trigger = screen.getByRole("button", { name: "打开菜单" });

    fireEvent.click(trigger);
    fireEvent.keyDown(document, { key: "Escape" });

    expect(screen.queryByRole("button", { name: "菜单项" })).not.toBeInTheDocument();
    expect(trigger).toHaveFocus();
    expect(onDismiss).toHaveBeenCalledTimes(1);
  });
});
