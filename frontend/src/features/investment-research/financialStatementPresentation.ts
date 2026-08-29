import { formatAmount } from "../../utils/format";

export type StatementRecord = Record<string, unknown>;

const PERIOD_LABEL_KEYS = ["REPORT_DATE_NAME", "报告期名称", "REPORT_DATE", "报告期", "报告日期", "REPORT_DATE_NOTICE", "REPORT_DATE_ORG"];
const PERIOD_SORT_KEYS = ["REPORT_DATE", "报告期", "报告日期", "REPORT_DATE_ORG", "REPORT_DATE_NOTICE"];
const DISCLOSURE_DATE_KEYS = ["UPDATE_DATE", "更新日期", "NOTICE_DATE", "公告日期"];
export const STATEMENT_METADATA_KEYS = new Set([
  ...PERIOD_LABEL_KEYS,
  "NOTICE_DATE", "公告日期", "REPORT_TYPE", "报告类型", "CURRENCY", "币种", "UPDATE_DATE", "更新日期",
  "SECUCODE", "SECURITY_CODE", "SECURITY_NAME_ABBR", "ORG_CODE", "ORG_TYPE", "SECURITY_TYPE_CODE",
]);

export interface StatementMetadata {
  label: string;
  value: string;
}

export type KeyFinancialMetricFormat = "amount" | "percent" | "multiple" | "eps";

export interface KeyFinancialMetric {
  key: string;
  label: string;
  format: KeyFinancialMetricFormat;
  values: Array<number | null>;
}

export interface KeyFinancialMetricGroup {
  key: "profitability" | "balance_health" | "cash_quality";
  label: string;
  periods: Array<{
    key: string;
    label: string;
    sortDate: string;
  }>;
  metrics: KeyFinancialMetric[];
}

const METADATA_LABELS: Record<string, string> = {
  NOTICE_DATE: "公告日期",
  公告日期: "公告日期",
  REPORT_TYPE: "报告类型",
  报告类型: "报告类型",
  CURRENCY: "币种",
  币种: "币种",
  UPDATE_DATE: "更新时间",
  更新日期: "更新时间",
};

function present(value: unknown) {
  return value !== null && value !== undefined && value !== "" && value !== "N/A";
}

function numericValue(record: StatementRecord, keys: string[]) {
  for (const key of keys) {
    const value = record[key];
    if (!present(value)) continue;
    const numeric = typeof value === "number" ? value : Number(value);
    if (Number.isFinite(numeric)) return numeric;
  }
  return null;
}

function ratio(numerator: number | null, denominator: number | null, scale = 1) {
  if (numerator === null || denominator === null || denominator === 0) return null;
  const value = numerator / denominator * scale;
  return Number.isFinite(value) ? value : null;
}

function normalizeDate(value: unknown) {
  if (!present(value)) return null;
  const text = String(value).trim();
  const compact = text.match(/^(\d{4})(\d{2})(\d{2})$/);
  if (compact) return `${compact[1]}-${compact[2]}-${compact[3]}`;
  const iso = text.match(/^(\d{4}-\d{2}-\d{2})/);
  return iso?.[1] ?? null;
}

export function statementPeriodLabel(record: StatementRecord, index: number) {
  for (const key of PERIOD_LABEL_KEYS) {
    if (present(record[key])) {
      return String(record[key]);
    }
  }
  return `第${index + 1}期`;
}

export function statementSortDate(record: StatementRecord) {
  for (const key of PERIOD_SORT_KEYS) {
    const value = normalizeDate(record[key]);
    if (value) return value;
  }
  return "";
}

function statementDisclosureDate(record: StatementRecord) {
  return DISCLOSURE_DATE_KEYS.reduce((latest, key) => {
    const value = normalizeDate(record[key]);
    return value && value > latest ? value : latest;
  }, "");
}

export function normalizeStatementRecords(records: StatementRecord[]) {
  const normalized = records
    .filter((record) => Object.values(record).some(present))
    .map((record, index) => {
      const sortDate = statementSortDate(record);
      return {
        key: `${sortDate || "period"}-${index}`,
        label: statementPeriodLabel(record, index),
        sortDate,
        disclosureDate: statementDisclosureDate(record),
        sourceIndex: index,
        record,
      };
    })
    .sort((left, right) => (
      right.sortDate.localeCompare(left.sortDate)
      || right.disclosureDate.localeCompare(left.disclosureDate)
      || left.sourceIndex - right.sourceIndex
    ));

  const seenPeriods = new Set<string>();
  return normalized.filter(({ label, sortDate }) => {
    const identity = sortDate ? `date:${sortDate}` : `label:${label}`;
    if (seenPeriods.has(identity)) return false;
    seenPeriods.add(identity);
    return true;
  });
}

export function statementMetricKeys(records: StatementRecord[]) {
  return Array.from(new Set(records.flatMap((record) => Object.keys(record))))
    .filter((key) => !STATEMENT_METADATA_KEYS.has(key) && records.some((record) => present(record[key])));
}

export function statementMetadata(record: StatementRecord): StatementMetadata[] {
  return Object.entries(METADATA_LABELS)
    .filter(([key]) => present(record[key]))
    .map(([key, label]) => ({
      label,
      value: key.includes("DATE") || key.includes("日期")
        ? normalizeDate(record[key]) ?? String(record[key])
        : String(record[key]),
    }));
}

export function formatStatementValue(rawKey: string, value: unknown) {
  if (!present(value)) return "-";
  if (typeof value !== "number" || !Number.isFinite(value)) return typeof value === "number" ? "-" : String(value);
  if (rawKey.endsWith("_YOY") || rawKey.includes("RATIO") || rawKey.includes("MARGIN")) {
    return `${value.toFixed(2)}%`;
  }
  if (rawKey.includes("EPS")) return value.toFixed(4);
  if (Math.abs(value) < 10_000 && !Number.isInteger(value)) {
    return value.toLocaleString("zh-CN", { maximumFractionDigits: 4 });
  }
  return formatAmount(value);
}

export function formatKeyFinancialMetricValue(
  value: number | null,
  format: KeyFinancialMetricFormat,
) {
  if (value === null || !Number.isFinite(value)) return "-";
  if (format === "percent") return `${value.toFixed(2)}%`;
  if (format === "multiple") return value.toFixed(2);
  if (format === "eps") return value.toFixed(4);
  return formatAmount(value);
}

const REVENUE_KEYS = ["OPERATE_INCOME", "TOTAL_OPERATE_INCOME", "BIZINCO", "BIZTOTINCO"];
const REVENUE_YOY_KEYS = REVENUE_KEYS.map((key) => `${key}_YOY`);
const OPERATING_COST_KEYS = ["OPERATE_COST", "TOTAL_OPERATE_COST", "BIZCOST", "BIZTOTCOST"];
const PARENT_PROFIT_KEYS = ["PARENT_NETPROFIT", "NETPARECOMPPROF", "NETPARESHARPROF", "NETPROFIT"];
const PARENT_PROFIT_YOY_KEYS = PARENT_PROFIT_KEYS.map((key) => `${key}_YOY`);
const DEDUCTED_PROFIT_KEYS = ["DEDUCT_PARENT_NETPROFIT"];
const DEDUCTED_PROFIT_YOY_KEYS = DEDUCTED_PROFIT_KEYS.map((key) => `${key}_YOY`);
const BASIC_EPS_KEYS = ["BASIC_EPS", "BASICEPS"];

const TOTAL_ASSET_KEYS = ["TOTAL_ASSETS", "TOTASSET"];
const TOTAL_LIABILITY_KEYS = ["TOTAL_LIABILITIES", "TOTLIAB"];
const CASH_KEYS = ["MONETARYFUNDS", "CURFDS"];
const INVENTORY_KEYS = ["INVENTORY", "INVE"];
const CURRENT_ASSET_KEYS = ["TOTAL_CURRENT_ASSETS", "TOTCURRASSET"];
const CURRENT_LIABILITY_KEYS = ["TOTAL_CURRENT_LIAB", "TOTALCURRLIAB"];

const OPERATING_CASH_FLOW_KEYS = ["NETCASH_OPERATE", "MANANETR"];
const OPERATING_CASH_FLOW_YOY_KEYS = OPERATING_CASH_FLOW_KEYS.map((key) => `${key}_YOY`);
const INVESTING_CASH_FLOW_KEYS = ["NETCASH_INVEST", "INVNETCASHFLOW"];

export function buildKeyFinancialMetricGroups(
  balance: StatementRecord[] = [],
  profit: StatementRecord[] = [],
  cashflow: StatementRecord[] = [],
): KeyFinancialMetricGroup[] {
  const normalizedProfit = normalizeStatementRecords(profit);
  const profitPeriods = normalizedProfit.slice(0, 4);
  const balancePeriods = normalizeStatementRecords(balance).slice(0, 4);
  const cashflowPeriods = normalizeStatementRecords(cashflow).slice(0, 4);
  const profitByPeriod = new Map(
    normalizedProfit
      .filter(({ sortDate }) => sortDate)
      .map(({ sortDate, record }) => [sortDate, record]),
  );

  const profitabilityMetrics: KeyFinancialMetric[] = [
    { key: "revenue", label: "营业收入", format: "amount", values: profitPeriods.map(({ record }) => numericValue(record, REVENUE_KEYS)) },
    { key: "revenue_yoy", label: "营收同比", format: "percent", values: profitPeriods.map(({ record }) => numericValue(record, REVENUE_YOY_KEYS)) },
    { key: "parent_profit", label: "归母净利润", format: "amount", values: profitPeriods.map(({ record }) => numericValue(record, PARENT_PROFIT_KEYS)) },
    { key: "parent_profit_yoy", label: "归母净利润同比", format: "percent", values: profitPeriods.map(({ record }) => numericValue(record, PARENT_PROFIT_YOY_KEYS)) },
    { key: "deducted_profit", label: "扣非归母净利润", format: "amount", values: profitPeriods.map(({ record }) => numericValue(record, DEDUCTED_PROFIT_KEYS)) },
    { key: "deducted_profit_yoy", label: "扣非归母净利润同比", format: "percent", values: profitPeriods.map(({ record }) => numericValue(record, DEDUCTED_PROFIT_YOY_KEYS)) },
    {
      key: "gross_margin",
      label: "毛利率",
      format: "percent",
      values: profitPeriods.map(({ record }) => {
        const revenue = numericValue(record, REVENUE_KEYS);
        const cost = numericValue(record, OPERATING_COST_KEYS);
        return revenue === null || cost === null ? null : ratio(revenue - cost, revenue, 100);
      }),
    },
    {
      key: "net_margin",
      label: "净利率",
      format: "percent",
      values: profitPeriods.map(({ record }) => (
        ratio(numericValue(record, PARENT_PROFIT_KEYS), numericValue(record, REVENUE_KEYS), 100)
      )),
    },
    { key: "basic_eps", label: "基本每股收益", format: "eps", values: profitPeriods.map(({ record }) => numericValue(record, BASIC_EPS_KEYS)) },
  ];

  const balanceMetrics: KeyFinancialMetric[] = [
    { key: "total_assets", label: "总资产", format: "amount", values: balancePeriods.map(({ record }) => numericValue(record, TOTAL_ASSET_KEYS)) },
    { key: "total_liabilities", label: "总负债", format: "amount", values: balancePeriods.map(({ record }) => numericValue(record, TOTAL_LIABILITY_KEYS)) },
    { key: "cash", label: "货币资金", format: "amount", values: balancePeriods.map(({ record }) => numericValue(record, CASH_KEYS)) },
    { key: "inventory", label: "存货", format: "amount", values: balancePeriods.map(({ record }) => numericValue(record, INVENTORY_KEYS)) },
    {
      key: "debt_ratio",
      label: "资产负债率",
      format: "percent",
      values: balancePeriods.map(({ record }) => (
        ratio(numericValue(record, TOTAL_LIABILITY_KEYS), numericValue(record, TOTAL_ASSET_KEYS), 100)
      )),
    },
    {
      key: "current_ratio",
      label: "流动比率",
      format: "multiple",
      values: balancePeriods.map(({ record }) => (
        ratio(numericValue(record, CURRENT_ASSET_KEYS), numericValue(record, CURRENT_LIABILITY_KEYS))
      )),
    },
  ];

  const cashMetrics: KeyFinancialMetric[] = [
    { key: "operating_cash_flow", label: "经营活动现金流净额", format: "amount", values: cashflowPeriods.map(({ record }) => numericValue(record, OPERATING_CASH_FLOW_KEYS)) },
    { key: "operating_cash_flow_yoy", label: "经营活动现金流同比", format: "percent", values: cashflowPeriods.map(({ record }) => numericValue(record, OPERATING_CASH_FLOW_YOY_KEYS)) },
    {
      key: "free_cash_flow",
      label: "自由现金流",
      format: "amount",
      values: cashflowPeriods.map(({ record }) => {
        const operating = numericValue(record, OPERATING_CASH_FLOW_KEYS);
        const investing = numericValue(record, INVESTING_CASH_FLOW_KEYS);
        return operating === null || investing === null ? null : operating + investing;
      }),
    },
    {
      key: "cash_profit_ratio",
      label: "现金利润比",
      format: "multiple",
      values: cashflowPeriods.map(({ record, sortDate }) => {
        const matchingProfit = sortDate ? profitByPeriod.get(sortDate) : undefined;
        return matchingProfit
          ? ratio(
            numericValue(record, OPERATING_CASH_FLOW_KEYS),
            numericValue(matchingProfit, PARENT_PROFIT_KEYS),
          )
          : null;
      }),
    },
  ];

  return [
    {
      key: "profitability",
      label: "盈利与增长",
      periods: profitPeriods.map(({ key, label, sortDate }) => ({ key, label, sortDate })),
      metrics: profitabilityMetrics,
    },
    {
      key: "balance_health",
      label: "资产健康",
      periods: balancePeriods.map(({ key, label, sortDate }) => ({ key, label, sortDate })),
      metrics: balanceMetrics,
    },
    {
      key: "cash_quality",
      label: "现金质量",
      periods: cashflowPeriods.map(({ key, label, sortDate }) => ({ key, label, sortDate })),
      metrics: cashMetrics,
    },
  ];
}
