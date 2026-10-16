import { fireEvent, render, screen } from "@testing-library/react";
import { describe, expect, it, vi } from "vitest";
import BackupRetentionCard from "./BackupRetentionCard";
import type { ConfigUpdate } from "../../../types/settings";

const renderCard = (formPartial: Partial<ConfigUpdate> = {}, onChange = vi.fn(), onSave = vi.fn()) => {
  render(
    <BackupRetentionCard
      form={formPartial as ConfigUpdate}
      onChange={onChange}
      onSave={onSave}
      isSaving={false}
    />,
  );
  return { onChange, onSave };
};

describe("BackupRetentionCard", () => {
  it("shows the persisted settings", () => {
    renderCard({
      database_backup_retention_count: 5,
      database_backup_include_market_daily: true,
      market_daily_backup_interval_days: 14,
      market_daily_backup_compression_level: 3,
    });
    expect(screen.getByRole("spinbutton", { name: "备份保留份数" })).toHaveValue("5");
    expect(screen.getByRole("switch", { name: "日线大库备份开关" })).toBeChecked();
    expect(screen.getByRole("spinbutton", { name: "大库备份周期" })).toHaveValue("14");
    expect(screen.getByRole("spinbutton", { name: "大库压缩级别" })).toHaveValue("3");
  });

  it("falls back to defaults when values are missing", () => {
    renderCard({});
    expect(screen.getByRole("spinbutton", { name: "备份保留份数" })).toHaveValue("3");
    expect(screen.getByRole("switch", { name: "日线大库备份开关" })).toBeChecked();
    expect(screen.getByRole("spinbutton", { name: "大库备份周期" })).toHaveValue("7");
    expect(screen.getByRole("spinbutton", { name: "大库压缩级别" })).toHaveValue("1");
  });

  it("emits the new settings and triggers save", () => {
    const { onChange, onSave } = renderCard({ database_backup_retention_count: 2 });
    fireEvent.change(screen.getByRole("spinbutton", { name: "备份保留份数" }), { target: { value: "4" } });
    expect(onChange).toHaveBeenCalledWith({ database_backup_retention_count: 4 });

    fireEvent.change(screen.getByRole("spinbutton", { name: "大库备份周期" }), { target: { value: "10" } });
    expect(onChange).toHaveBeenCalledWith({ market_daily_backup_interval_days: 10 });

    fireEvent.change(screen.getByRole("spinbutton", { name: "大库压缩级别" }), { target: { value: "2" } });
    expect(onChange).toHaveBeenCalledWith({ market_daily_backup_compression_level: 2 });

    fireEvent.click(screen.getByRole("switch", { name: "日线大库备份开关" }));
    expect(onChange).toHaveBeenCalledWith({ database_backup_include_market_daily: false });

    fireEvent.click(screen.getByRole("button", { name: /保存备份/ }));
    expect(onSave).toHaveBeenCalledTimes(1);
  });
});