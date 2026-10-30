import { fireEvent, render, screen, waitFor } from "@testing-library/react";
import { RouterProvider, createMemoryRouter, useNavigate } from "react-router-dom";
import { beforeEach, describe, expect, it } from "vitest";
import SettingsLeaveBlocker from "./SettingsLeaveBlocker";

function StartPage() {
  const navigate = useNavigate();
  return <button type="button" onClick={() => navigate("/other")}>去其它页面</button>;
}

function renderBlocker(hasUnsavedChanges: boolean, dirtyCardCount = 0) {
  const router = createMemoryRouter(
    [
      {
        path: "/settings",
        element: (
          <>
            <SettingsLeaveBlocker hasUnsavedChanges={hasUnsavedChanges} dirtyCardCount={dirtyCardCount} />
            <StartPage />
          </>
        ),
      },
      { path: "/other", element: <div>其它页面内容</div> },
    ],
    { initialEntries: ["/settings"] },
  );
  render(<RouterProvider router={router} />);
  return router;
}

describe("SettingsLeaveBlocker", () => {
  beforeEach(() => {
    document.body.innerHTML = "";
  });

  it("lets the user leave freely when nothing is dirty", async () => {
    renderBlocker(false);

    fireEvent.click(screen.getByRole("button", { name: "去其它页面" }));

    expect(await screen.findByText("其它页面内容")).toBeInTheDocument();
    expect(screen.queryByRole("dialog")).not.toBeInTheDocument();
  });

  it("asks for confirmation when leaving with unsaved changes and can cancel", async () => {
    const router = renderBlocker(true, 2);

    fireEvent.click(screen.getByRole("button", { name: "去其它页面" }));

    expect(await screen.findByRole("dialog")).toBeInTheDocument();
    expect(screen.getByRole("dialog")).toHaveAccessibleName(/有未保存的配置变更/);
    expect(screen.getByText(/当前有 2 张配置卡片尚未保存/)).toBeInTheDocument();

    fireEvent.click(screen.getByRole("button", { name: /留在本页/ }));

    await waitFor(() => expect(screen.queryByText("其它页面内容")).not.toBeInTheDocument());
    expect(router.state.location.pathname).toBe("/settings");
  });

  it("navigates away after confirming the discard", async () => {
    const router = renderBlocker(true, 1);

    fireEvent.click(screen.getByRole("button", { name: "去其它页面" }));
    expect(await screen.findByRole("dialog")).toBeInTheDocument();
    expect(screen.getByRole("dialog")).toHaveAccessibleName(/有未保存的配置变更/);

    fireEvent.click(screen.getByRole("button", { name: /放弃修改并离开/ }));

    expect(await screen.findByText("其它页面内容")).toBeInTheDocument();
    await waitFor(() => expect(router.state.location.pathname).toBe("/other"));
  });
});
