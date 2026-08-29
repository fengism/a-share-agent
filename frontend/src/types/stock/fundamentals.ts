export interface RevenueBreakdownItem {
  id: string | null;
  class_name: string;
  is_sub_item: boolean | null;
  revenue: number | null;
  cost: number | null;
  gross_profit: number | null;
  revenue_share_pct: number | null;
  gross_margin_pct: number | null;
}

export interface RevenueBreakdown {
  code: string;
  symbol: string;
  name: string;
  source: "sina";
  amount_unit: "CNY_yuan";
  amount_unit_inferred: boolean;
  by_product: RevenueBreakdownItem[];
  by_business: RevenueBreakdownItem[];
  by_region: RevenueBreakdownItem[];
}

export interface FundamentalExportData {
  balance: Record<string, unknown>[];
  profit: Record<string, unknown>[];
  cashflow: Record<string, unknown>[];
  revenueBreakdown: RevenueBreakdown;
}
