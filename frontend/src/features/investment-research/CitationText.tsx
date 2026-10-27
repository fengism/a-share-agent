import { renderWithCitations } from "./citationRendering";

export default function CitationText({
  text,
  className,
}: {
  text: string;
  className?: string;
}) {
  return <span className={className}>{renderWithCitations(text)}</span>;
}
