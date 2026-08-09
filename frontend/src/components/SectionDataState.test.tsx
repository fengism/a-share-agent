import { fireEvent, render, screen } from "@testing-library/react";
import { describe, expect, it, vi } from "vitest";
import SectionDataState from "./SectionDataState";

describe("SectionDataState", () => {
  it("prioritizes loading over error, empty, and content", () => {
    render(
      <SectionDataState isLoading error={new Error("failed")} isEmpty emptyText="无数据">
        <div>内容</div>
      </SectionDataState>,
    );

    expect(screen.getByLabelText("数据加载中")).toBeInTheDocument();
    expect(screen.queryByText("failed")).not.toBeInTheDocument();
    expect(screen.queryByText("内容")).not.toBeInTheDocument();
  });

  it("shows an error with retry", () => {
    const onRetry = vi.fn();
    render(
      <SectionDataState error={new Error("network failed")} onRetry={onRetry}>
        <div>内容</div>
      </SectionDataState>,
    );

    expect(screen.getByText("network failed")).toBeInTheDocument();
    fireEvent.click(screen.getByRole("button", { name: /重\s*试/ }));
    expect(onRetry).toHaveBeenCalledOnce();
  });

  it("shows an empty state before rendering content", () => {
    const { rerender } = render(
      <SectionDataState isEmpty emptyText="暂无指标">
        <div>业务内容</div>
      </SectionDataState>,
    );
    expect(screen.getByText("暂无指标")).toBeInTheDocument();

    rerender(
      <SectionDataState>
        <div>业务内容</div>
      </SectionDataState>,
    );
    expect(screen.getByText("业务内容")).toBeInTheDocument();
  });
});
