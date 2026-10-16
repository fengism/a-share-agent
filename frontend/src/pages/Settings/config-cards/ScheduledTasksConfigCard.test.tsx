import { fireEvent, render, screen } from "@testing-library/react";
import { describe, expect, it, vi } from "vitest";
import ScheduledTasksConfigCard from "./ScheduledTasksConfigCard";
import type { ConfigUpdate } from "../../../types/settings";

const renderCard = (formPartial: Partial<ConfigUpdate> = {}, onChange = vi.fn(), onSave = vi.fn()) => {
  render(
    <ScheduledTasksConfigCard
      form={formPartial as ConfigUpdate}
      onChange={onChange}
      onSave={onSave}
      isSaving={false}
    />,
  );
  return { onChange, onSave };
};

describe("ScheduledTasksConfigCard", () => {
  it("renders persisted switch states", () => {
    renderCard({
      daily_review_prewarm_enabled: true,
      macro_analysis_prewarm_enabled: false,
      potential_stock_daily_enabled: true,
      stock_valuation_snapshot_refresh_enabled: false,
    });

    expect(screen.getByRole("switch", { name: "每日复盘自动预热开关" })).toBeChecked();
    expect(screen.getByRole("switch", { name: "宏观分析自动预热开关" })).not.toBeChecked();
    expect(screen.getByRole("switch", { name: "潜在牛股每日扫描开关" })).toBeChecked();
    expect(screen.getByRole("switch", { name: "股票估值快照自动刷新开关" })).not.toBeChecked();
  });

  it("defaults to all false when values are not provided", () => {
    renderCard({});

    expect(screen.getByRole("switch", { name: "每日复盘自动预热开关" })).not.toBeChecked();
    expect(screen.getByRole("switch", { name: "宏观分析自动预热开关" })).not.toBeChecked();
    expect(screen.getByRole("switch", { name: "潜在牛股每日扫描开关" })).not.toBeChecked();
    expect(screen.getByRole("switch", { name: "股票估值快照自动刷新开关" })).not.toBeChecked();
  });

  it("toggles switches and invokes onChange and onSave", () => {
    const { onChange, onSave } = renderCard({
      daily_review_prewarm_enabled: false,
      macro_analysis_prewarm_enabled: false,
    });

    fireEvent.click(screen.getByRole("switch", { name: "每日复盘自动预热开关" }));
    expect(onChange).toHaveBeenCalledWith({ daily_review_prewarm_enabled: true });

    fireEvent.click(screen.getByRole("switch", { name: "宏观分析自动预热开关" }));
    expect(onChange).toHaveBeenCalledWith({ macro_analysis_prewarm_enabled: true });

    fireEvent.click(screen.getByRole("switch", { name: "潜在牛股每日扫描开关" }));
    expect(onChange).toHaveBeenCalledWith({ potential_stock_daily_enabled: true });

    fireEvent.click(screen.getByRole("switch", { name: "股票估值快照自动刷新开关" }));
    expect(onChange).toHaveBeenCalledWith({ stock_valuation_snapshot_refresh_enabled: true });

    fireEvent.click(screen.getByRole("button", { name: /保存后台任务/ }));
    expect(onSave).toHaveBeenCalledTimes(1);
  });
});
