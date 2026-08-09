import ReactMarkdown from "react-markdown";
import remarkGfm from "remark-gfm";
import { tryExtractFromJson } from "./reportHelpers";
import "./industry-report.css";

const markdownPlugins = [remarkGfm];

export default function MarkdownReport({ content }: { content: string }) {
  let text = content?.trim() || "";

  if (text.startsWith("{") || text.startsWith("[")) {
    text = tryExtractFromJson(text);
  }

  const codeBlockMatch = text.match(/^```(?:markdown|md)?\s*([\s\S]*?)```$/);
  if (codeBlockMatch) text = codeBlockMatch[1].trim();

  return (
    <div className="industry-markdown">
      <ReactMarkdown
        remarkPlugins={markdownPlugins}
        components={{
          table: ({ children }) => (
            <div className="industry-markdown-table-wrap">
              <table>{children}</table>
            </div>
          ),
        }}
      >
        {text}
      </ReactMarkdown>
    </div>
  );
}
