import type { IndustryChainEvidence, IndustryChainResult } from "../../types/stock";

const referencePattern = /(?:证据(?:\s*ID)?\s*[:：]?\s*)?`?(?<![a-z0-9_])(ev_[a-z0-9_-]+)(?![a-z0-9_])`?/gi;
const urlPattern = /https?:\/\/[^\s<>"')\]]+/gi;
const protectedFields = new Set(["evidence_id", "evidence_ids", "summary_evidence_ids", "positioning_evidence_ids", "url", "source_url", "source_urls", "pdf_url", "href"]);

export function readableReferences(text: string, catalog: IndustryChainEvidence[] = []): string {
  const labels = new Map(catalog.map((item, index) => [item.evidence_id.toLowerCase(), `资料 ${index + 1}`]));
  const replace = (part: string) => part.replace(referencePattern, (_, id: string) => labels.get(id.toLowerCase()) || "相关资料");
  let offset = 0;
  const parts: string[] = [];
  for (const match of text.matchAll(urlPattern)) {
    parts.push(replace(text.slice(offset, match.index)), match[0]);
    offset = (match.index ?? 0) + match[0].length;
  }
  parts.push(replace(text.slice(offset)));
  return parts.join("");
}

export function reportPresentation(result: IndustryChainResult): IndustryChainResult {
  const walk = (value: unknown, field = ""): unknown => {
    if (protectedFields.has(field)) return value;
    if (typeof value === "string") return readableReferences(value, result.evidence_catalog);
    if (Array.isArray(value)) return value.map(item => walk(item, field));
    if (value && typeof value === "object") return Object.fromEntries(Object.entries(value).map(([key, item]) => [key, walk(item, key)]));
    return value;
  };
  return walk(result) as IndustryChainResult;
}
