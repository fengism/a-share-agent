import {
  generatedFinancialFieldLabels,
  generatedSinaFinancialFieldLabels,
} from "../api/generated/financialFieldLabels";

export type FinancialStatementType = "balance" | "profit" | "cashflow";

export const financialFieldLabels: Record<string, string> = generatedFinancialFieldLabels;

function isReadableChinese(value: string) {
  return /[㐀-鿿]/.test(value);
}

function unknownFinancialLabel(rawKey: string) {
  let hash = 0;
  for (const character of rawKey) {
    hash = (hash * 31 + character.charCodeAt(0)) >>> 0;
  }
  return `其他财务字段（${(hash % 10_000).toString().padStart(4, "0")}）`;
}

export function formatFinancialFieldLabel(
  rawKey: string,
  statementType?: FinancialStatementType,
) {
  const scopedLabel = statementType
    ? generatedSinaFinancialFieldLabels[statementType]?.[rawKey]
    : undefined;
  return scopedLabel
    ?? generatedFinancialFieldLabels[rawKey]
    ?? (isReadableChinese(rawKey) ? rawKey : unknownFinancialLabel(rawKey));
}
