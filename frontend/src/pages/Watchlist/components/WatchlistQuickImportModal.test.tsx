import { fireEvent, render, screen, waitFor } from "@testing-library/react";
import { describe, expect, it, vi } from "vitest";
import { WatchlistQuickImportModal } from "./WatchlistQuickImportModal";

describe("WatchlistQuickImportModal", () => {
  it("renders preset groups and disables already existing stocks", () => {
    const onClose = vi.fn();
    const onImport = vi.fn().mockResolvedValue(undefined);

    render(
      <WatchlistQuickImportModal
        open={true}
        onClose={onClose}
        existingCodes={["600519"]}
        onImport={onImport}
      />,
    );

    expect(screen.getByText("快速加自选 · 预设主题股票池")).toBeInTheDocument();
    expect(screen.getByText("宁德时代")).toBeInTheDocument();
    expect(screen.getByText("贵州茅台")).toBeInTheDocument();

    // 宁德时代未添加，点击选中
    fireEvent.click(screen.getByText("宁德时代"));
    const confirmBtn = screen.getByRole("button", { name: /一键导入选中\s*\(1\)/ });
    expect(confirmBtn).not.toBeDisabled();

    fireEvent.click(confirmBtn);
    waitFor(() => {
      expect(onImport).toHaveBeenCalledWith([expect.objectContaining({ code: "300750" })]);
    });
  });
});
