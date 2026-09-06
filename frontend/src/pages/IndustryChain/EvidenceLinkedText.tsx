import type { ReactNode } from "react";
import type { IndustryChainEvidence } from "../../types/stock";

const EVIDENCE_REFERENCE_PATTERN = /证据(?:\s*ID)?\s*[:：]?\s*(ev_[a-z0-9_-]+)\b|\b(ev_[a-z0-9_-]+)\b/gi;

interface EvidenceLink {
  label: string;
  url?: string;
}

function safeExternalUrl(value?: string): URL | undefined {
  if (!value) return undefined;
  try {
    const url = new URL(value.trim());
    return url.protocol === "http:" || url.protocol === "https:" ? url : undefined;
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
  const url = evidence?.source_urls
    ?.map((candidate) => safeExternalUrl(candidate))
    .find((candidate): candidate is URL => Boolean(candidate));

  if (!url) return { label: "相关证据" };

  return {
    label: evidence?.title?.trim() || url.hostname.replace(/^www\./i, ""),
    url: url.toString(),
  };
}

function renderEvidenceLinkedText(
  text: string,
  evidenceCatalog: IndustryChainEvidence[] = [],
): ReactNode {
  const matches = [...text.matchAll(EVIDENCE_REFERENCE_PATTERN)];
  if (matches.length === 0) return text;

  const parts: ReactNode[] = [];
  let cursor = 0;
  for (const match of matches) {
    const start = match.index ?? 0;
    if (start > cursor) parts.push(text.slice(cursor, start));

    const evidenceId = match[1] || match[2];
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
