import { cleanup, fireEvent, render, screen, waitFor, within } from "@testing-library/react";
import { BrowserRouter } from "react-router-dom";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import StockProfileTab from "./StockProfileTab";
import { message, Modal } from "antd";
import { apiDownload, apiGet } from "../../api/client";

const mocks = vi.hoisted(() => ({
  enrich: vi.fn(), refetchRecords: vi.fn(), refetchSummary: vi.fn(), update: vi.fn(), sync: vi.fn(),
  recordsError: null as Error | null, summaryError: null as Error | null,
  importing: false, importFile: vi.fn(),
}));
vi.mock("../../api/client", async (importOriginal) => ({
  ...await importOriginal<typeof import("../../api/client")>(),
  apiDownload: vi.fn(), apiGet: vi.fn(),
}));

const mockSummary = {
  total: 5555,
  has_business_count: 3200,
  has_listing_date_count: 5555,
  market_group_counts: { A: 5555, HK: 642 },
  board_counts: { 主板: 3194, 创业板: 1405, 科创板: 616 },
  last_updated_at: "2026-09-05 00:00:00",
};

const mockRecords = {
  items: [
    {
      revision: "a".repeat(64),
      id: 1,
      market_group: "A",
      exchange: "SH",
      board: "主板",
      stock_code: "600519.SH",
      stock_name: "贵州茅台",
      listing_date: "2001-08-27",
      main_business: "茅台酒及系列酒的生产与销售。",
      business_scope: "茅台酒及系列酒的生产与销售...",
      products: "茅台酒",
      industry: "饮料制造",
      sw_level1_name: "食品饮料",
      sw_level2_name: "白酒Ⅱ",
      sw_level3_name: "白酒Ⅲ",
      city: "仁怀市",
      province: "贵州",
      legal_repr: "陈华",
      registered_capital: "12.50亿",
      setup_date: "1999-11-20",
      website: "www.moutaichina.com",
      company_intro: "贵州茅台酒股份有限公司简介",
      source: "exchange_master_sync",
      source_version: "v1",
      is_manual_override: false,
      created_at: "2026-09-05 00:00:00",
      updated_at: "2026-09-05 00:00:00",
    },
  ],
  total: 1,
  page: 1,
  page_size: 50,
};

vi.mock("../../api/queries", () => ({
  useStockProfileSummary: () => ({
    data: mockSummary,
    isLoading: false,
    error: mocks.summaryError,
    refetch: mocks.refetchSummary,
  }),
  useStockProfileRecords: () => ({
    data: mockRecords,
    error: mocks.recordsError,
    isLoading: false,
    isFetching: false,
    refetch: mocks.refetchRecords,
  }),
  useCreateStockProfileRecord: () => ({
    mutateAsync: vi.fn(),
    isPending: false,
  }),
  useUpdateStockProfileRecord: () => ({
    mutateAsync: mocks.update,
    isPending: false,
  }),
  useDeleteStockProfileRecord: () => ({
    mutateAsync: vi.fn(),
    isPending: false,
  }),
  useEnrichStockProfileRecord: () => ({
    mutateAsync: mocks.enrich,
    isPending: false,
  }),
  useSyncMasterStockProfiles: () => ({
    mutateAsync: mocks.sync,
    isPending: false,
  }),
  useImportStockProfiles: () => ({
    mutate: mocks.importFile,
    isPending: mocks.importing,
  }),
}));

describe("StockProfileTab", () => {
  beforeEach(() => {
    vi.clearAllMocks();
    mocks.recordsError = null;
    mocks.summaryError = null;
    mocks.importing = false;
    const resolved = Promise.resolve(true);
    const notice = Object.assign(() => {}, { then: resolved.then.bind(resolved) });
    vi.spyOn(message, "success").mockReturnValue(notice);
    vi.spyOn(message, "error").mockReturnValue(notice);
    vi.spyOn(message, "info").mockReturnValue(notice);
    mocks.refetchRecords.mockResolvedValue({ data: mockRecords });
    vi.mocked(apiDownload).mockResolvedValue(undefined);
  });
  afterEach(() => { cleanup(); vi.restoreAllMocks(); });

  function openPage() {
    render(<BrowserRouter><StockProfileTab /></BrowserRouter>);
  }

  it("exports the selected missing-business filter", async () => {
    openPage();
    fireEvent.mouseDown(screen.getAllByRole("combobox")[2]);
    fireEvent.click(await screen.findByText("待补充主营"));
    fireEvent.click(screen.getByRole("button", { name: /导出 CSV/ }));
    await waitFor(() => expect(apiDownload).toHaveBeenCalledWith(
      "/stock-profile/records/export", "stock_profile_export.csv",
      expect.objectContaining({ has_business: false }),
    ));
  });

  it("shows a business failure rather than a success toast", async () => {
    mocks.enrich.mockResolvedValue({ success: false, updated_fields: [], message: "上游未返回有效资料" });
    openPage();
    fireEvent.click(screen.getByRole("button", { name: "补充资料" }));
    await waitFor(() => expect(message.error).toHaveBeenCalledWith("上游未返回有效资料"));
    expect(message.success).not.toHaveBeenCalled();
  });

  it("loads the latest drawer record after enrichment", async () => {
    mocks.enrich.mockResolvedValue({ success: true, updated_fields: ["main_business"], message: "补充成功" });
    vi.mocked(apiGet).mockResolvedValue({ ...mockRecords.items[0], main_business: "最新主营资料" });
    openPage();
    fireEvent.click(screen.getByRole("button", { name: "查看完整资料" }));
    fireEvent.click(await screen.findByRole("button", { name: /在线补充资料/ }));
    expect(await screen.findByText("最新主营资料")).toBeInTheDocument();
  });

  it("keeps hidden fields when saving and submits explicit empty fields", async () => {
    mocks.update.mockResolvedValue(mockRecords.items[0]);
    openPage();
    fireEvent.click(screen.getByRole("button", { name: "编辑资料" }));
    fireEvent.change(await screen.findByLabelText("主营业务"), { target: { value: "" } });
    fireEvent.click(screen.getByRole("button", { name: /保.*存/ }));
    await waitFor(() => expect(mocks.update).toHaveBeenCalledWith({
      id: 1, record: expect.objectContaining({ main_business: "", city: "仁怀市", expected_revision: "a".repeat(64), exchange: "SH" }),
    }));
  });

  it("preserves the editor after a revision conflict", async () => {
    mocks.update.mockRejectedValue(new Error("记录已被其他操作更新，请重新加载"));
    openPage();
    fireEvent.click(screen.getByRole("button", { name: "编辑资料" }));
    fireEvent.change(await screen.findByLabelText("主营业务"), { target: { value: "我的修改" } });
    expect(screen.getByLabelText("申万一级行业")).toBeDisabled();
    fireEvent.click(screen.getByRole("button", { name: /保.*存/ }));
    await waitFor(() => expect(message.error).toHaveBeenCalledWith("记录已被其他操作更新，请重新加载"));
    expect(screen.getByLabelText("主营业务")).toHaveValue("我的修改");
    expect(mocks.update.mock.calls[0][0].record).not.toHaveProperty("sw_level1_name");
  });

  it("reports partial sync with stale exchange and timestamp", async () => {
    const warning = vi.spyOn(Modal, "warning").mockReturnValue({ destroy: vi.fn(), update: vi.fn() });
    mocks.sync.mockResolvedValue({ added: 1, updated: 2, unchanged: 3, skipped: 4,
      complete: false, failed_exchanges: { SH: "offline" }, stale_exchanges: ["SH"], fetched_at: { SH: 12345 } });
    openPage();
    fireEvent.click(screen.getByRole("button", { name: /同步交易所名录/ }));
    fireEvent.click(await screen.findByRole("button", { name: /OK/ }));
    await waitFor(() => expect(warning).toHaveBeenCalledWith(expect.objectContaining({
      title: expect.stringContaining("部分完成"),
      content: expect.stringContaining("使用旧数据：SH"),
    })));
    expect(message.success).not.toHaveBeenCalled();
  });

  it("shows list errors with retry rather than stale rows or empty data", () => {
    mocks.recordsError = new Error("数据库暂时不可用");
    openPage();
    expect(screen.getByText("个股资料加载失败")).toBeInTheDocument();
    expect(screen.queryByText("贵州茅台")).not.toBeInTheDocument();
    fireEvent.click(screen.getByRole("button", { name: /重.*试/ }));
    expect(mocks.refetchRecords).toHaveBeenCalledTimes(1);
  });

  it("shows summary failure independently of the available list", () => {
    mocks.summaryError = new Error("概览请求失败");
    openPage();
    expect(screen.getByText("个股资料概览加载失败")).toBeInTheDocument();
    expect(screen.getByText("贵州茅台")).toBeInTheDocument();
    fireEvent.click(screen.getByRole("button", { name: /重.*试/ }));
    expect(mocks.refetchSummary).toHaveBeenCalledTimes(1);
  });

  it("clears file and overwrite flag when import is cancelled and reopened", async () => {
    openPage();
    fireEvent.click(screen.getByRole("button", { name: /批量导入/ }));
    const modal = await screen.findByRole("dialog");
    fireEvent.click(within(modal).getByRole("checkbox"));
    const input = modal.querySelector('input[type="file"]') as HTMLInputElement;
    fireEvent.change(input, { target: { files: [new File(["股票代码\n600519.SH"], "test.csv", { type: "text/csv" })] } });
    await waitFor(() => expect(within(modal).getByRole("button", { name: /开始导入/ })).toBeEnabled());
    fireEvent.click(within(modal).getByRole("button", { name: /取.*消/ }));
    fireEvent.click(screen.getByRole("button", { name: /批量导入/ }));
    const reopened = await screen.findByRole("dialog");
    expect(within(reopened).getByRole("checkbox")).not.toBeChecked();
    expect(within(reopened).getByRole("button", { name: /开始导入/ })).toBeDisabled();
    expect(within(reopened).queryByText("test.csv")).not.toBeInTheDocument();
    expect(mocks.importFile).not.toHaveBeenCalled();
  });

  it("renders stock profile summary statistics and records table", () => {
    render(
      <BrowserRouter>
        <StockProfileTab />
      </BrowserRouter>
    );

    // Verify statistics
    expect(screen.getByText("全市场股票数")).toBeInTheDocument();
    expect(screen.getAllByText("5,555").length).toBeGreaterThanOrEqual(1);
    expect(screen.getByText("主营业务已录入")).toBeInTheDocument();
    expect(screen.getByText("上市时间已建档")).toBeInTheDocument();

    // Verify table records
    expect(screen.getByText("600519.SH")).toBeInTheDocument();
    expect(screen.getByText("贵州茅台")).toBeInTheDocument();
    expect(screen.getByText("2001-08-27")).toBeInTheDocument();
    expect(screen.getByText("茅台酒及系列酒的生产与销售。")).toBeInTheDocument();
  });
});
