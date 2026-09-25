import { readableReferences } from "./reportPresentation";
import type { ReactNode } from "react";
import type { IndustryChainEvidence } from "../../types/stock";


interface EvidenceLink {
  label: string;
  url?: string;
}

function safeExternalUrl(value?: string): URL | undefined {
  if (!value) return undefined;
  try {
    const url = new URL(value.trim());
    return (url.protocol === "http:" || url.protocol === "https:") && !url.username && !url.password ? url : undefined;
  } catch {
    return undefined;
  }
}

function evidenceLink(
  evidenceId: string,
  evidenceCatalog: IndustryChainEvidence[],
): EvidenceLink {
  const evidence = evidenceCatalog.find(
    (item) => item.evidence_id.toLowerCase() === evidenceId.toLowerCase(),
  );
  const urls = evidence?.source_urls
    ?.map((candidate) => safeExternalUrl(candidate))
    .filter((candidate): candidate is URL => Boolean(candidate)) || [];
  const uniqueUrls = [...new Map(urls.map(url => [url.href, url])).values()];
  const url = uniqueUrls.length === 1 ? uniqueUrls[0] : undefined;

  if (!url) return { label: "相关证据" };

  return {
    label: (evidence?.title?.trim() ? readableReferences(evidence.title) : "") || url.hostname.replace(/^www\./i, ""),
    url: url.toString(),
  };
}

function renderEvidenceLinkedText(
  text: string,
  evidenceCatalog: IndustryChainEvidence[] = [],
): ReactNode {
  // Parent report replaces raw IDs; still resolve readable labels to source links.
  const pattern = /证据(?:\s*ID)?\s*[:：]?\s*(ev_[a-z0-9_-]+)\b|\b(ev_[a-z0-9_-]+)\b|资料 (\d+)(?!\d)/gi;
  const matches = [...text.matchAll(pattern)];
  if (matches.length === 0) return text;

  const parts: ReactNode[] = [];
  let cursor = 0;
  for (const match of matches) {
    const start = match.index ?? 0;
    if (start > cursor) parts.push(text.slice(cursor, start));

    const evidenceId = match[1] || match[2] || evidenceCatalog[Number(match[3]) - 1]?.evidence_id;
    if (!evidenceId) { parts.push(match[0]); cursor = start + match[0].length; continue; }
    const link = evidenceLink(evidenceId, evidenceCatalog);
    parts.push(
      link.url ? (
        <a
          key={`${evidenceId}-${start}`}
          href={link.url}
          target="_blank"
          rel="noreferrer"
          title="查看证据原文"
          className="industry-evidence-link"
        >
          {link.label}
        </a>
      ) : (
        <span key={`${evidenceId}-${start}`}>{link.label}</span>
      ),
    );
    cursor = start + match[0].length;
  }
  if (cursor < text.length) parts.push(text.slice(cursor));
  return <>{parts}</>;
}

export default function EvidenceLinkedText({
  text,
  evidenceCatalog = [],
}: {
  text: string;
  evidenceCatalog?: IndustryChainEvidence[];
}) {
  return <>{renderEvidenceLinkedText(text, evidenceCatalog)}</>;
}
