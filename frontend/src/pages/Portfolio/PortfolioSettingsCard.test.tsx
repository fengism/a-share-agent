import { fireEvent, render, screen, waitFor } from "@testing-library/react";
import { beforeEach, describe, expect, it, vi } from "vitest";
import PortfolioSettingsCard from "./PortfolioSettingsCard";

const mocks = vi.hoisted(() => ({
  updateSettings: vi.fn(),
}));

vi.mock("../../api/queries", () => ({
  useUpdatePortfolioSettings: () => ({
    mutateAsync: mocks.updateSettings,
    isPending: false,
  }),
}));

describe("PortfolioSettingsCard", () => {
  beforeEach(() => {
    mocks.updateSettings.mockReset().mockResolvedValue({});
  });

  it("saves initial cash and position limits", async () => {
    render(<PortfolioSettingsCard settings={{
      initial_cash: null,
      max_total_position_pct: 80,
      max_single_stock_pct: 30,
      max_sector_pct: 40,
      updated_at: null,
    }} />);

    fireEvent.change(screen.getByRole("spinbutton", { name: "初始资金" }), { target: { value: "100000" } });
    fireEvent.change(screen.getByRole("spinbutton", { name: "总仓位上限" }), { target: { value: "75" } });
    fireEvent.click(screen.getByRole("button", { name: /保存设置/ }));

    await waitFor(() => expect(mocks.updateSettings).toHaveBeenCalledTimes(1));
    expect(mocks.updateSettings).toHaveBeenCalledWith({
      initial_cash: 100000,
      max_total_position_pct: 75,
      max_single_stock_pct: 30,
      max_sector_pct: 40,
    });
  });

  it("syncs form values when refreshed settings change", async () => {
    const { rerender } = render(<PortfolioSettingsCard settings={{
      initial_cash: null,
      max_total_position_pct: 80,
      max_single_stock_pct: 30,
      max_sector_pct: 40,
      updated_at: null,
    }} />);

    rerender(<PortfolioSettingsCard settings={{
      initial_cash: 200000,
      max_total_position_pct: 70,
      max_single_stock_pct: 25,
      max_sector_pct: 35,
      updated_at: "2026-09-19T12:00:00",
    }} />);

    await waitFor(() => {
      expect(screen.getByRole("spinbutton", { name: "初始资金" })).toHaveValue("200000.00");
      expect(screen.getByRole("spinbutton", { name: "总仓位上限" })).toHaveValue("70.00");
      expect(screen.getByRole("spinbutton", { name: "单股仓位上限" })).toHaveValue("25.00");
      expect(screen.getByRole("spinbutton", { name: "行业仓位上限" })).toHaveValue("35.00");
    });
  });

});
