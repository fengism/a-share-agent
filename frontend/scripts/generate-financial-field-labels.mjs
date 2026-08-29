import { readFileSync, writeFileSync } from "node:fs";

const sourcePath = new URL("../../backend/app/constants/financial_labels.json", import.meta.url);
const outputPath = new URL("../src/api/generated/financialFieldLabels.ts", import.meta.url);
const source = JSON.parse(readFileSync(sourcePath, "utf8"));

function requiredRecord(value, name) {
  if (!value || typeof value !== "object" || Array.isArray(value)) {
    throw new Error(`财报标签缺少对象: ${name}`);
  }
  for (const [key, label] of Object.entries(value)) {
    if (!key || typeof label !== "string" || !/[㐀-鿿]/.test(label)) {
      throw new Error(`财报标签无效: ${name}.${key}`);
    }
  }
  return value;
}

function sortedRecord(value) {
  return Object.fromEntries(Object.entries(value).sort(([left], [right]) => left.localeCompare(right)));
}

const rawLabels = sortedRecord(requiredRecord(source.FINANCIAL_RAW_FIELD_LABELS, "FINANCIAL_RAW_FIELD_LABELS"));
const sinaSource = source.SINA_FINANCIAL_FIELD_LABELS;
if (!sinaSource || typeof sinaSource !== "object" || Array.isArray(sinaSource)) {
  throw new Error("财报标签缺少对象: SINA_FINANCIAL_FIELD_LABELS");
}
for (const statement of ["balance", "profit", "cashflow"]) requiredRecord(sinaSource[statement], `SINA_FINANCIAL_FIELD_LABELS.${statement}`);
const sinaLabels = Object.fromEntries(
  Object.entries(sinaSource)
    .sort(([left], [right]) => left.localeCompare(right))
    .map(([statement, labels]) => [statement, sortedRecord(labels)]),
);

const content = `// This file is generated from backend/app/constants/financial_labels.json.\n// Run \`npm run api:generate\`; do not edit manually.\n\nexport const generatedFinancialFieldLabels: Record<string, string> = ${JSON.stringify(rawLabels, null, 2)};\n\nexport const generatedSinaFinancialFieldLabels: Record<string, Record<string, string>> = ${JSON.stringify(sinaLabels, null, 2)};\n`;

writeFileSync(outputPath, content, "utf8");
