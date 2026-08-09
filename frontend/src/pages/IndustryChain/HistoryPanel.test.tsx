import { fireEvent, render, screen, waitFor } from "@testing-library/react";
import { describe, expect, it, vi } from "vitest";
import type { IndustryChainHistoryItem } from "../../types/stock";
import HistoryPanel from "./HistoryPanel";

const history: IndustryChainHistoryItem[] = [
  {
    name: "AI 芯片",
    archive_id: "20260804_210000",
    saved_at: "2026-08-04T21:00:00",
    title: "AI 芯片产业链",
    summary: "产业链摘要",
    can_delete: true,
  },
];

function renderHistoryPanel(embedded = false, items = history) {
  const onFilterChange = vi.fn();
  const onLoadArchive = vi.fn();
  const onDelete = vi.fn().mockResolvedValue(undefined);

  const view = render(
    <HistoryPanel
      history={items}
      filter=""
      activeName="AI 芯片"
      archiveId="20260804_210000"
      isLoading={false}
      error={null}
      hasMore={false}
      isLoadingMore={false}
      loadingArchiveKey=""
      deletingArchiveKey=""
      embedded={embedded}
      onFilterChange={onFilterChange}
      onLoadArchive={onLoadArchive}
      onDelete={onDelete}
      onLoadMore={vi.fn()}
      onRetry={vi.fn()}
    />,
  );

  return { ...view, onDelete, onFilterChange, onLoadArchive };
}

describe("IndustryChain HistoryPanel", () => {
  it("renders without a duplicate card title when embedded in a drawer", () => {
    renderHistoryPanel(true);

    expect(screen.queryByText("历史产业链")).not.toBeInTheDocument();
    expect(screen.getByRole("button", { pressed: true })).toHaveTextContent("AI 芯片产业链");
  });

  it("keeps filtering and archive selection available", () => {
    const { container, onFilterChange, onLoadArchive } = renderHistoryPanel();

    expect(screen.getByText("历史产业链")).toBeInTheDocument();
    fireEvent.change(screen.getByPlaceholderText("按名称过滤"), { target: { value: "芯片" } });
    fireEvent.click(screen.getByRole("button", { pressed: true }));

    expect(onFilterChange).toHaveBeenCalledWith("芯片");
    expect(onLoadArchive).toHaveBeenCalledWith(history[0]);
    expect(screen.getByRole("list")).toBeInTheDocument();
    expect(screen.getAllByRole("listitem")).toHaveLength(1);
    expect(container.querySelector(".ant-list")).not.toBeInTheDocument();
  });

  it("confirms deletion without loading the archive", async () => {
    const { onDelete, onLoadArchive } = renderHistoryPanel();

    fireEvent.click(screen.getByRole("button", { name: "删除 AI 芯片产业链 记录" }));
    fireEvent.click(await screen.findByRole("button", { name: /^删\s*除$/ }));

    await waitFor(() => expect(onDelete).toHaveBeenCalledWith(history[0]));
    expect(onLoadArchive).not.toHaveBeenCalled();
  });

  it("hides deletion for read-only legacy records", () => {
    renderHistoryPanel(false, [{ ...history[0], can_delete: false }]);

    expect(screen.queryByRole("button", { name: /删除 .* 记录/ })).not.toBeInTheDocument();
  });
});
