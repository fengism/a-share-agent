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
  /** sina=A股（金额+占比）；ths=港股同花顺 F10（只有占比，金额为空） */
  source: "sina" | "ths";
  /** 港股口径不声明币种（同花顺表头随公司报表而定，且金额本身缺失） */
  amount_unit: "CNY_yuan" | null;
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
