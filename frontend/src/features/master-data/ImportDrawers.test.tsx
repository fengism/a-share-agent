import { cleanup, fireEvent, render, screen, waitFor, within } from "@testing-library/react";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import StockConceptTab from "./StockConceptTab";
import IndustryClassificationTab from "./IndustryClassificationTab";

const mocks = vi.hoisted(() => ({
  error: null as Error | null, pending: false, retry: vi.fn(), preview: vi.fn(), commit: vi.fn(),
}));
vi.mock("../../store/authStore", () => ({ useAuthStore: () => true }));
vi.mock("../../api/queries", () => {
  const query = () => ({ data: undefined, isLoading: false, refetch: mocks.retry });
  const records = () => ({ data: { items: [], total: 0 }, isLoading: false, error: mocks.error, refetch: mocks.retry });
  const mutation = () => ({ isPending: false, mutate: vi.fn() });
  const preview = () => ({ isPending: mocks.pending, mutate: mocks.preview });
  const commit = () => ({ isPending: false, mutate: mocks.commit });
  return {
    useStockConceptStatus: query, useConceptTags: query, useStockConceptRecords: records,
    useCreateStockConceptRecord: mutation, useUpdateStockConceptRecord: mutation, useDeleteStockConceptRecord: mutation,
    usePreviewStockConceptImport: preview, useCommitStockConceptImport: commit,
    useTriggerStockConceptEnrich: mutation,
    useIndustryStatus: query, useIndustryHierarchy: query, useIndustryRecords: records,
    useCreateIndustryRecord: mutation, useUpdateIndustryRecord: mutation, useDeleteIndustryRecord: mutation,
    useUpdateIndustryRefreshPolicy: mutation, useRefreshIndustries: mutation,
    usePreviewIndustryImport: preview, useCommitIndustryImport: commit,
  };
});

describe.each([
  ["概念", StockConceptTab, "概念记录加载失败"],
  ["行业", IndustryClassificationTab, "行业记录加载失败"],
] as const)("%s data management", (_name, Component, title) => {
  beforeEach(() => { vi.clearAllMocks(); mocks.error = null; mocks.pending = false; });
  afterEach(cleanup);

  it("shows query failures and offers retry", () => {
    mocks.error = new Error("网络不可用");
    render(<Component />);
    expect(screen.getByText(title)).toBeInTheDocument();
    fireEvent.click(screen.getByRole("button", { name: /重.*试/ }));
    expect(mocks.retry).toHaveBeenCalledTimes(1);
  });

  it("locks file selection and closing while preview is in flight", async () => {
    const { rerender } = render(<Component />);
    fireEvent.click(screen.getByRole("button", { name: /批量导入/ }));
    await screen.findByRole("dialog");
    mocks.pending = true;
    rerender(<Component />);
    const drawer = screen.getByRole("dialog");
    expect(drawer.querySelector('input[type="file"]')).toBeDisabled();
    expect(within(drawer).getByRole("button", { name: /预检文件/ })).toBeDisabled();
    expect(within(drawer).queryByRole("button", { name: "Close" })).not.toBeInTheDocument();
    fireEvent.keyDown(drawer, { key: "Escape", keyCode: 27 });
    expect(screen.getByRole("dialog")).toBeInTheDocument();
  });

  it("does not reuse a selected file after closing the import drawer", async () => {
    render(<Component />);
    fireEvent.click(screen.getByRole("button", { name: /批量导入/ }));
    const drawer = await screen.findByRole("dialog");
    const input = drawer.querySelector('input[type="file"]') as HTMLInputElement;
    fireEvent.change(input, { target: { files: [new File(["code,data"], "first.csv", { type: "text/csv" })] } });
    await waitFor(() => expect(within(drawer).getByRole("button", { name: /预检文件/ })).toBeEnabled());
    await waitFor(() => expect(within(drawer).getByRole("button", { name: /预检文件/ })).not.toHaveClass("ant-btn-loading"));
    fireEvent.click(within(drawer).getByRole("button", { name: /预检文件/ }));
    expect(mocks.preview).toHaveBeenCalledWith(expect.objectContaining({ filename: "first.csv" }), expect.anything());
    fireEvent.click(within(drawer).getByRole("button", { name: "Close" }));
    fireEvent.click(screen.getByRole("button", { name: /批量导入/ }));
    const reopened = await screen.findByRole("dialog");
    expect(within(reopened).getByRole("button", { name: /预检文件/ })).toBeDisabled();
    expect(within(reopened).queryByText("first.csv")).not.toBeInTheDocument();
    expect(mocks.commit).not.toHaveBeenCalled();
  });
});
