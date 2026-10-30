import { render } from "@testing-library/react";
import { createElement } from "react";
import { RouterProvider, createMemoryRouter } from "react-router-dom";
import { describe, expect, it, vi } from "vitest";
import { useUnsavedChangesGuard } from "./useUnsavedChangesGuard";

function GuardHost({ hasUnsavedChanges }: { hasUnsavedChanges: boolean }) {
  useUnsavedChangesGuard({ hasUnsavedChanges });
  return <div>host</div>;
}

/** hook 依赖 useBlocker，必须跑在 data router 里 */
function renderGuard(hasUnsavedChanges: boolean) {
  const router = createMemoryRouter(
    [{ path: "*", element: createElement(GuardHost, { hasUnsavedChanges }) }],
    { initialEntries: ["/form"] },
  );
  render(createElement(RouterProvider, { router }));
  return router;
}

describe("useUnsavedChangesGuard", () => {
  it("registers beforeunload only while there are unsaved changes", () => {
    const addSpy = vi.spyOn(window, "addEventListener");

    renderGuard(true);
    expect(addSpy).toHaveBeenCalledWith("beforeunload", expect.any(Function));

    addSpy.mockClear();
    renderGuard(false);
    expect(addSpy).not.toHaveBeenCalledWith("beforeunload", expect.any(Function));

    addSpy.mockRestore();
  });

  it("cancels a page unload while unsaved changes exist", () => {
    renderGuard(true);

    const event = new Event("beforeunload", { cancelable: true });
    const preventDefault = vi.spyOn(event, "preventDefault");
    window.dispatchEvent(event);

    expect(preventDefault).toHaveBeenCalled();
  });
});
