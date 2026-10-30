import { render, screen } from "@testing-library/react";
import { describe, expect, it, vi } from "vitest";
import { ResearchCardExportModal } from "./ResearchCardExportModal";

describe("ResearchCardExportModal", () => {
  it("renders report card preview with disclaimer and export buttons", () => {
    const onClose = vi.fn();
    render(
      <ResearchCardExportModal
        open={true}
        onClose={onClose}
        content="## 深度研报\n贵州茅台估值处于近五年低位。"
        messageId="msg-12345678"
      />,
    );

    expect(screen.getByText("导出投研报告卡片")).toBeInTheDocument();
    expect(screen.getByText("A股智能投研快报")).toBeInTheDocument();
    expect(screen.getByText(/贵州茅台估值处于近五年低位/)).toBeInTheDocument();
    expect(screen.getByText(/免责声明/)).toBeInTheDocument();
    expect(screen.getByRole("button", { name: /保存图片/ })).toBeInTheDocument();
    expect(screen.getByRole("button", { name: /复制长图/ })).toBeInTheDocument();
  });
});
