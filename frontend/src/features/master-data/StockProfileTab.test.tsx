import { render, screen } from "@testing-library/react";
import { BrowserRouter } from "react-router-dom";
import { describe, expect, it, vi } from "vitest";
import StockProfileTab from "./StockProfileTab";

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
    refetch: vi.fn(),
  }),
  useStockProfileRecords: () => ({
    data: mockRecords,
    isLoading: false,
    isFetching: false,
    refetch: vi.fn(),
  }),
  useCreateStockProfileRecord: () => ({
    mutateAsync: vi.fn(),
    isPending: false,
  }),
  useUpdateStockProfileRecord: () => ({
    mutateAsync: vi.fn(),
    isPending: false,
  }),
  useDeleteStockProfileRecord: () => ({
    mutateAsync: vi.fn(),
    isPending: false,
  }),
  useEnrichStockProfileRecord: () => ({
    mutateAsync: vi.fn(),
    isPending: false,
  }),
  useSyncMasterStockProfiles: () => ({
    mutateAsync: vi.fn(),
    isPending: false,
  }),
  useImportStockProfiles: () => ({
    mutate: vi.fn(),
    isPending: false,
  }),
}));

describe("StockProfileTab", () => {
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
