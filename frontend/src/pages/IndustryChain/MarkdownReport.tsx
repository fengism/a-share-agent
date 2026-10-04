import ReactMarkdown from "react-markdown";
import remarkBreaks from "remark-breaks";
import remarkGfm from "remark-gfm";
import { readableReferences } from "./reportPresentation";
import { tryExtractFromJson } from "./reportHelpers";
import type { IndustryChainEvidence } from "../../types/stock";
import "./industry-report.css";

const markdownPlugins = [remarkGfm, remarkBreaks];

function linkifyEvidence(text: string, catalog: IndustryChainEvidence[] = []): string {
  const processed = readableReferences(text, catalog);
  if (catalog.length === 0) return processed;

  // Don't re-link if already inside a markdown link: [label](url)
  const pattern = /(?:\[[^\]]+\]\([^)]+\))|(资料\s*(\d+)(?!\d))/g;
  return processed.replace(pattern, (match, _link, indexStr) => {
    if (!indexStr) return match;
    const idx = Number(indexStr) - 1;
    const evidence = catalog[idx];
    const urls = evidence?.source_urls?.filter(Boolean) || [];
    const url = urls.length > 0 ? urls[0] : undefined;
    if (url) {
      return `[资料 ${indexStr}](${url})`;
    }
    return `资料 ${indexStr}`;
  });
}

export default function MarkdownReport({
  content,
  evidenceCatalog = [],
  className = "",
}: {
  content: string;
  evidenceCatalog?: IndustryChainEvidence[];
  className?: string;
}) {
  let text = content?.trim() || "";

  if (text.startsWith("{") || text.startsWith("[")) {
    text = tryExtractFromJson(text);
  }

  const codeBlockMatch = text.match(/^```(?:markdown|md)?\s*([\s\S]*?)```$/);
  if (codeBlockMatch) text = codeBlockMatch[1].trim();

  text = linkifyEvidence(text, evidenceCatalog);

  return (
    <div className={`industry-markdown ${className}`.trim()}>
      <ReactMarkdown
        remarkPlugins={markdownPlugins}
        components={{
          table: ({ children }) => (
            <div className="industry-markdown-table-wrap">
              <table>{children}</table>
            </div>
          ),
          a: ({ href, children, ...props }) => {
            const isExternal = href?.startsWith("http://") || href?.startsWith("https://");
            return (
              <a
                href={href}
                target={isExternal ? "_blank" : undefined}
                rel={isExternal ? "noreferrer" : undefined}
                className={isExternal ? "industry-evidence-link" : undefined}
                {...props}
              >
                {children}
              </a>
            );
          },
        }}
      >
        {text}
      </ReactMarkdown>
    </div>
  );
}

