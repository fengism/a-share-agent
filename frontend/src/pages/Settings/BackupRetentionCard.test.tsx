import { fireEvent, render, screen } from "@testing-library/react";
import { describe, expect, it, vi } from "vitest";
import BackupRetentionCard from "./BackupRetentionCard";
import type { ConfigUpdate } from "../../types/settings";

const renderCard = (value: number | undefined, onChange = vi.fn(), onSave = vi.fn()) => {
  render(
    <BackupRetentionCard
      form={{ database_backup_retention_count: value } as ConfigUpdate}
      onChange={onChange}
      onSave={onSave}
      isSaving={false}
    />,
  );
  return { onChange, onSave };
};

describe("BackupRetentionCard", () => {
  it("shows the persisted retention count", () => {
    renderCard(5);
    expect(screen.getByRole("spinbutton")).toHaveValue("5");
  });

  it("falls back to two when the value is missing", () => {
    renderCard(undefined);
    expect(screen.getByRole("spinbutton")).toHaveValue("2");
  });

  it("emits the new count and triggers save", () => {
    const { onChange, onSave } = renderCard(2);
    fireEvent.change(screen.getByRole("spinbutton"), { target: { value: "4" } });
    expect(onChange).toHaveBeenCalledWith({ database_backup_retention_count: 4 });
    fireEvent.click(screen.getByRole("button", { name: /保存备份份数/ }));
    expect(onSave).toHaveBeenCalledTimes(1);
  });
});