import { fireEvent, render, screen } from "@testing-library/react";
import { beforeEach, describe, expect, it, vi } from "vitest";
import { useAuthStore } from "../../store/authStore";
import SavedFilterToolbar from "./SavedFilterToolbar";
import { DEFAULT_SCREENER_FILTERS } from "../../features/screener/screenerUrlState";

vi.mock("antd", async (importOriginal) => {
  const actual = await importOriginal<typeof import("antd")>();
  return { ...actual, message: { success: vi.fn(), warning: vi.fn() } };
});

describe("SavedFilterToolbar", () => {
  beforeEach(() => {
    window.localStorage.clear();
    useAuthStore.setState({
      user: { id: 7, username: "tester", is_admin: false, must_change_password: false },
      bootstrapped: true,
    });
  });

  it("saves the current filter state for the active user", () => {
    render(
      <SavedFilterToolbar
        state={{
          filters: { ...DEFAULT_SCREENER_FILTERS, pe_max: 15 },
          showPercentile: false,
          pePercentileMax: 50,
          pbPercentileMax: 50,
        }}
        onApply={vi.fn()}
      />,
    );

    fireEvent.change(screen.getByRole("textbox", { name: "筛选方案名称" }), { target: { value: "低估值" } });
    fireEvent.click(screen.getByRole("button", { name: /保存条件/ }));

    expect(window.localStorage.getItem("screener-filters:user:7")).toContain("低估值");
  });
});
